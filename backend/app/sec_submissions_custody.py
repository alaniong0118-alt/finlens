"""Handle-relative local NTFS custody; dormant until explicitly supplied offline.

No path rename, replacement, deletion, provisioning or authority promotion. Native
acceptance is a separate gate. Trusted operator/admin/SYSTEM/kernel can tamper;
hashes establish local consistency only. Flush+rename is not power-loss durability.
"""

from dataclasses import dataclass
import ctypes as c
import hashlib
import re
import sys


CUSTODY_REVISION = "fl-ucr-01c1.custody.v1"
BLOCK = 65_536
MAX_BODY = 4_194_304
MAX_RECEIPT = 16_384
ANCESTOR_ACCESS = READER_ACCESS = 0x1200A1
ROOT_ACCESS = 0x1200A7
SOURCE_ACCESS = 0x1300A7
WRITER_ACCESS = 0xC0120000
FILE_READER_ACCESS = 0x80120000
SHARE_RW, SHARE_RWD, SHARE_R = 3, 7, 1
STATUS_PENDING = 0x103
STATUS_COLLISION = 0xC0000035
# Deliberately process-retained if terminal observation becomes impossible. Never
# free buffers/IOSB or close pending handles. No automatic reap/refetch/retry.
_PENDING = []


class CustodyError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise CustodyError(code)


class _StatusPointer(c.Union):
    _fields_ = [("Status", c.c_int32), ("Pointer", c.c_void_p)]


class IO_STATUS_BLOCK(c.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("u", _StatusPointer), ("Information", c.c_size_t)]


class FILE_RENAME_INFORMATION(c.Structure):
    _fields_ = [("ReplaceIfExists", c.c_ubyte), ("RootDirectory", c.c_void_p),
                ("FileNameLength", c.c_uint32), ("FileName", c.c_uint16 * 1)]


class UNICODE_STRING(c.Structure):
    _fields_ = [("Length", c.c_uint16), ("MaximumLength", c.c_uint16),
                ("Buffer", c.c_void_p)]


class OBJECT_ATTRIBUTES(c.Structure):
    _fields_ = [("Length", c.c_uint32), ("RootDirectory", c.c_void_p),
                ("ObjectName", c.POINTER(UNICODE_STRING)), ("Attributes", c.c_uint32),
                ("SecurityDescriptor", c.c_void_p), ("SecurityQualityOfService", c.c_void_p)]


def assert_layout():
    require(c.sizeof(c.c_void_p) == 8, "windows_x64_only")
    require([getattr(FILE_RENAME_INFORMATION, name).offset for name in
             ("ReplaceIfExists", "RootDirectory", "FileNameLength", "FileName")]
            == [0, 8, 16, 20], "rename_layout")
    require(c.sizeof(IO_STATUS_BLOCK) == 16 and c.alignment(IO_STATUS_BLOCK) == 8
            and IO_STATUS_BLOCK.Information.offset == 8, "iosb_layout")


def classify_status(status):
    """Only STATUS_SUCCESS is supported terminal success; signed 32-bit NTSTATUS."""
    raw = c.c_uint32(status).value
    if raw == STATUS_PENDING:
        return "pending"
    if raw == 0:
        return "success"
    if raw == STATUS_COLLISION:
        return "collision"
    if c.c_int32(raw).value < 0:
        return "failure"
    return "indeterminate"


def component(name):
    require(type(name) is str and 0 < len(name) <= 255 and name not in (".", "..")
            and not any(ch in '\\/:*?"<>|' or ord(ch) < 32 for ch in name)
            and name[-1] not in " .", "component")
    require(name.split(".")[0].upper() not in
            {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)),
             *(f"LPT{i}" for i in range(10))}, "component")
    return name


def bundle_name(identifier, suffix):
    require(type(identifier) is str and re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        identifier) is not None, "capture_id")
    require(suffix in ("staging", "complete"), "bundle_suffix")
    return f"capture-{identifier}.{suffix}"


@dataclass(frozen=True)
class RootSpec:
    """Inert provisioned root descriptor; never discovers or creates a root."""

    volume_path: str
    components: tuple
    volume_serial: int
    file_id: str
    security_sha256: str
    operator_sid: str

    def validate(self):
        require(type(self.volume_path) is str and re.fullmatch(
            r"\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}\\", self.volume_path) is not None,
            "volume_path")
        require(type(self.components) is tuple and 1 <= len(self.components) <= 64,
                "root_components")
        for item in self.components:
            component(item)
        require(type(self.volume_serial) is int and 0 <= self.volume_serial < 2**64,
                "root_serial")
        require(type(self.file_id) is str and re.fullmatch(r"[0-9a-f]{32}", self.file_id)
                is not None, "root_file_id")
        require(type(self.security_sha256) is str and re.fullmatch(
            r"[0-9a-f]{64}", self.security_sha256) is not None, "root_security")
        require(type(self.operator_sid) is str and re.fullmatch(r"S-1-[0-9-]{1,180}",
                self.operator_sid) is not None, "operator_sid")

    @property
    def final_path(self):
        return self.volume_path + "\\".join(self.components)


class WindowsAPI:
    """Typed native seam. Constructed only by an explicitly opened store.

    All native calls use retained handles. Signed NTSTATUS is never Boolean-tested
    or interpreted through GetLastError. Win32 BOOL calls have separate checks.
    """

    def __init__(self):
        require(sys.platform == "win32", "windows_only")
        assert_layout()
        kernel = c.WinDLL("kernel32", use_last_error=True)
        security = c.WinDLL("advapi32", use_last_error=True)
        native = c.WinDLL("ntdll")
        P, U32, PTR = c.POINTER, c.c_uint32, c.c_void_p

        def bind(lib, name, result, args):
            function = getattr(lib, name)
            function.restype, function.argtypes = result, args
            setattr(self, name, function)

        bind(native, "NtCreateFile", c.c_int32,
             [P(PTR), U32, P(OBJECT_ATTRIBUTES), P(IO_STATUS_BLOCK), PTR,
              U32, U32, U32, U32, PTR, U32])
        bind(native, "NtSetInformationFile", c.c_int32,
             [PTR, P(IO_STATUS_BLOCK), PTR, U32, c.c_int32])
        bind(native, "NtQueryDirectoryFile", c.c_int32,
             [PTR, PTR, PTR, PTR, P(IO_STATUS_BLOCK), PTR, U32, c.c_int32,
              c.c_ubyte, P(UNICODE_STRING), c.c_ubyte])
        bind(kernel, "WaitForSingleObject", U32, [PTR, U32])
        bind(kernel, "CloseHandle", c.c_int, [PTR])
        bind(kernel, "GetFileInformationByHandleEx", c.c_int, [PTR, c.c_int, PTR, U32])
        bind(kernel, "GetFinalPathNameByHandleW", U32, [PTR, c.c_wchar_p, U32, U32])
        bind(kernel, "GetVolumeInformationByHandleW", c.c_int,
             [PTR, c.c_wchar_p, U32, P(U32), P(U32), P(U32), c.c_wchar_p, U32])
        bind(kernel, "GetDriveTypeW", U32, [c.c_wchar_p])
        bind(kernel, "SetFilePointerEx", c.c_int, [PTR, c.c_int64, P(c.c_int64), U32])
        bind(kernel, "ReadFile", c.c_int, [PTR, PTR, U32, P(U32), PTR])
        bind(kernel, "WriteFile", c.c_int, [PTR, PTR, U32, P(U32), PTR])
        bind(kernel, "FlushFileBuffers", c.c_int, [PTR])
        bind(kernel, "LocalFree", PTR, [PTR])
        bind(security, "ConvertSidToStringSidW", c.c_int, [PTR, P(PTR)])
        bind(security, "GetSecurityInfo", U32,
             [PTR, c.c_int, U32, P(PTR), P(PTR), P(PTR), P(PTR), P(PTR)])
        bind(security, "GetSecurityDescriptorLength", U32, [PTR])
        bind(security, "GetAclInformation", c.c_int, [PTR, PTR, U32, c.c_int])
        bind(security, "GetAce", c.c_int, [PTR, U32, P(PTR)])

    def close(self, handle):
        require(self.CloseHandle(handle) != 0, "close_handle")

    def _terminal(self, status, handle, ios, storage, op, *, publication=True):
        if classify_status(status) != "pending":
            return status
        # storage, ios and op's handle ledger remain strongly referenced here.
        interrupted = False
        unknown = "publication_indeterminate" if publication else "native_io_indeterminate"
        while True:
            try:
                # Finite waits observe cancellation, but pending storage is never
                # freed at budget expiry. This is intentionally cooperative.
                wait = self.WaitForSingleObject(handle, 50)
                if wait == 0:
                    terminal = int(ios.Status)
                    if classify_status(terminal) == "pending":
                        raise CustodyError("pending_observation")
                    if interrupted:
                        op.note(CustodyError(unknown))
                    return terminal
                require(wait == 0x102, "pending_observation")
                try:
                    op.checkpoint()
                except CustodyError as error:
                    op.note(error)
            except (KeyboardInterrupt, SystemExit):
                interrupted = True
                op.note(CustodyError(unknown))
            except BaseException:
                # Cannot prove completion. Deliberately retain everything, even
                # beyond this operation. No closure against an in-flight buffer.
                op.quarantined = True
                _PENDING.append((self, storage, ios, handle, op))
                raise CustodyError(unknown) from None

    def open(self, parent, name, access, share, directory, create, op):
        if parent is not None:
            component(name)
        encoded = name.encode("utf-16-le")
        require(len(encoded) < 65534, "native_name_size")
        buf = c.create_unicode_buffer(name)
        us = UNICODE_STRING(len(encoded), len(encoded) + 2, c.cast(buf, c.c_void_p))
        oa = OBJECT_ATTRIBUTES(c.sizeof(OBJECT_ATTRIBUTES), parent, c.pointer(us),
                               0x1040, None, None)  # DONT_REPARSE | CASE_INSENSITIVE
        handle, ios = c.c_void_p(), IO_STATUS_BLOCK()
        ios.Status = STATUS_PENDING
        try:
            status = self.NtCreateFile(c.byref(handle), access, c.byref(oa), c.byref(ios),
                                       None, 0, share, 2 if create else 1,
                                       0x200000 | 0x20 | (1 if directory else 0x40), None, 0)
        except BaseException:
            if handle.value:
                op.own(handle.value, self.close, native=True)
            op.quarantined = True
            _PENDING.append((self, (buf, us, oa, handle), ios, handle.value, op))
            raise CustodyError("native_io_indeterminate") from None
        # Register even anomalous partial handles before status/checkpoint logic.
        token = op.own(handle.value, self.close, native=True) if handle.value else None
        status = self._terminal(status, handle.value, ios, (buf, us, oa, handle), op,
                                publication=False)
        require(classify_status(status) == "success" and token is not None,
                "native_open_or_collision")
        require(ios.Information == (2 if create else 1), "native_open_disposition")
        return handle.value, token

    def rename(self, handle, root, name, op):
        component(name)
        require(re.fullmatch(r"capture-[0-9a-f-]{36}\.complete", name) is not None,
                "rename_name")
        encoded = name.encode("utf-16-le")
        size = FILE_RENAME_INFORMATION.FileName.offset + len(encoded)
        # uint64 storage gives the required 8-byte alignment and zero padding.
        storage = (c.c_uint64 * ((size + 7) // 8))()
        info = c.cast(storage, c.POINTER(FILE_RENAME_INFORMATION)).contents
        info.ReplaceIfExists, info.RootDirectory, info.FileNameLength = 0, root, len(encoded)
        c.memmove(c.addressof(storage) + 20, encoded, len(encoded))
        ios = IO_STATUS_BLOCK()
        ios.Status = STATUS_PENDING
        try:
            status = self.NtSetInformationFile(handle, c.byref(ios), storage, size, 10)
        except BaseException:
            op.quarantined = True
            _PENDING.append((self, storage, ios, handle, op))
            raise CustodyError("publication_indeterminate") from None
        return self._terminal(status, handle, ios, storage, op)

    def sid(self, pointer):
        output = c.c_void_p()
        require(self.ConvertSidToStringSidW(pointer, c.byref(output)) != 0, "sid_query")
        try:
            return c.wstring_at(output.value)
        finally:
            self.LocalFree(output)

    def observe(self, handle):
        class ID(c.Structure):
            _fields_ = [("volume", c.c_uint64), ("id", c.c_ubyte * 16)]

        class TAG(c.Structure):
            _fields_ = [("attributes", c.c_uint32), ("tag", c.c_uint32)]

        class STANDARD(c.Structure):
            _fields_ = [("allocation", c.c_int64), ("length", c.c_int64),
                        ("links", c.c_uint32), ("delete", c.c_ubyte), ("directory", c.c_ubyte)]

        class ACLINFO(c.Structure):
            _fields_ = [("count", c.c_uint32), ("used", c.c_uint32), ("free", c.c_uint32)]

        fid, tag, standard = ID(), TAG(), STANDARD()
        for kind, value in ((18, fid), (9, tag), (1, standard)):
            require(self.GetFileInformationByHandleEx(handle, kind, c.byref(value),
                                                     c.sizeof(value)) != 0, "file_information")
        path = c.create_unicode_buffer(32768)
        size = self.GetFinalPathNameByHandleW(handle, path, len(path), 1)
        require(0 < size < len(path), "native_final_path")
        fs, serial, maximum, flags = (c.create_unicode_buffer(32), c.c_uint32(),
                                       c.c_uint32(), c.c_uint32())
        require(self.GetVolumeInformationByHandleW(handle, None, 0, c.byref(serial),
                c.byref(maximum), c.byref(flags), fs, len(fs)) != 0, "volume_information")
        volume = path.value.split("}\\", 1)[0] + "}\\"
        require(self.GetDriveTypeW(volume) == 3, "local_fixed_volume")
        owner, dacl, sd = c.c_void_p(), c.c_void_p(), c.c_void_p()
        require(self.GetSecurityInfo(handle, 1, 5, c.byref(owner), None,
                c.byref(dacl), None, c.byref(sd)) == 0, "security_query")
        try:
            require(bool(dacl.value), "null_dacl")
            length = self.GetSecurityDescriptorLength(sd)
            require(0 < length <= 65536, "security_size")
            acl = ACLINFO()
            require(self.GetAclInformation(dacl, c.byref(acl), c.sizeof(acl), 2) != 0
                    and acl.count <= 64, "acl_information")
            aces = []
            for i in range(acl.count):
                pointer = c.c_void_p()
                require(self.GetAce(dacl, i, c.byref(pointer)) != 0, "ace_query")
                header = c.string_at(pointer.value, 4)
                require(header[0] == 0 and int.from_bytes(header[2:4], "little") >= 12,
                        "unsupported_ace")
                aces.append((self.sid(pointer.value + 8),
                             c.c_uint32.from_address(pointer.value + 4).value, header[1], header[0]))
            return dict(volume_serial=fid.volume, file_id=bytes(fid.id).hex(), final_path=path.value,
                        security_sha256=hashlib.sha256(c.string_at(sd.value, length)).hexdigest(),
                        directory=bool(standard.directory), length=standard.length, links=standard.links,
                        filesystem=fs.value, attributes=tag.attributes, reparse_tag=tag.tag,
                        delete_pending=bool(standard.delete), owner_sid=self.sid(owner), aces=tuple(aces))
        finally:
            if sd.value:
                self.LocalFree(sd)

    def names(self, handle, op):
        # FILE_NAMES_INFORMATION, class 12; bounded listing of exactly two files.
        names, restart = [], True
        while True:
            data, ios = (c.c_uint64 * 8192)(), IO_STATUS_BLOCK()
            ios.Status = STATUS_PENDING
            try:
                status = self.NtQueryDirectoryFile(handle, None, None, None, c.byref(ios),
                    data, c.sizeof(data), 12, 0, None, int(restart))
            except BaseException:
                op.quarantined = True
                _PENDING.append((self, data, ios, handle, op))
                raise CustodyError("native_io_indeterminate") from None
            status = self._terminal(status, handle, ios, data, op, publication=False)
            if c.c_uint32(status).value == 0x80000006:  # STATUS_NO_MORE_FILES
                return tuple(sorted(names))
            require(classify_status(status) == "success" and 12 <= ios.Information <= c.sizeof(data),
                    "directory_listing")
            raw, offset = bytes(data)[:ios.Information], 0
            while True:
                require(offset + 12 <= len(raw), "directory_listing")
                following = int.from_bytes(raw[offset:offset + 4], "little")
                length = int.from_bytes(raw[offset + 8:offset + 12], "little")
                require(length % 2 == 0 and 0 < length <= 510
                        and offset + 12 + length <= len(raw), "directory_listing")
                name = raw[offset + 12:offset + 12 + length].decode("utf-16-le")
                if name not in (".", ".."):
                    names.append(name)
                    require(len(names) <= 2, "bundle_members")
                if not following:
                    break
                require(following >= 12 + length and offset + following < len(raw), "directory_listing")
                offset += following
            restart = False
            op.checkpoint()

    def rewind(self, handle):
        require(self.SetFilePointerEx(handle, 0, None, 0) != 0, "rewind")

    def read(self, handle, count):
        require(0 < count <= BLOCK, "read_bound")
        buf, actual = c.create_string_buffer(count), c.c_uint32()
        require(self.ReadFile(handle, buf, count, c.byref(actual), None) != 0, "read_file")
        return buf.raw[:actual.value]

    def write(self, handle, data):
        require(type(data) is bytes and 0 < len(data) <= BLOCK, "write_bound")
        buf, actual = c.create_string_buffer(data), c.c_uint32()
        require(self.WriteFile(handle, buf, len(data), c.byref(actual), None) != 0, "write_file")
        return actual.value

    def flush(self, handle):
        require(self.FlushFileBuffers(handle) != 0, "flush_file")


def _identity(observation):
    return tuple(observation[k] for k in ("volume_serial", "file_id", "security_sha256", "directory"))


class WindowsStore:
    """Opened inside Operation through an inert descriptor. No borrowed handles.

    The optional api is a trusted offline mock seam. A real WindowsAPI must never
    be used in default tests. Root provisioning/authorization is out of scope.
    """

    def __init__(self, op, spec, api=None):
        self.op, self.spec = op, spec
        self.root = None
        self.chain = []
        self.tokens = []
        require(type(spec) is RootSpec, "root_spec_type")
        op.call(spec.validate)
        self.api = op.call(WindowsAPI) if api is None else api
        self._open_root()

    def _open(self, parent, name, access, share, directory=True, create=False):
        self.op.checkpoint()
        # API registers partial handles before returning. No borrowed numeric
        # handle is registered twice or ever closed by an implicit finalizer.
        handle, token = self.api.open(parent, name, access, share, directory, create, self.op)
        self.tokens.append(token)
        self.op.checkpoint()
        return handle, token

    def _observe(self, handle, path, directory, *, private):
        obs = self.op.call(self.api.observe, handle)
        require(obs["filesystem"] == "NTFS" and obs["directory"] is directory
                and obs["final_path"] == path and not obs["delete_pending"]
                and obs["reparse_tag"] == 0 and not obs["attributes"] &
                (0x400 | 0x1000 | 0x40000 | 0x400000), "custody_attributes")
        require(obs["volume_serial"] == self.spec.volume_serial, "custody_volume")
        require(directory or obs["links"] == 1, "custody_hardlink")
        trusted = {self.spec.operator_sid, "S-1-5-18", "S-1-5-32-544"}
        require(obs["owner_sid"] in trusted, "custody_owner")
        aces = obs["aces"]
        require(0 < len(aces) <= 64, "custody_acl")
        for sid, mask, flags, kind in aces:
            require(kind == 0 and not flags & ~0x13, "custody_acl")
            if private:
                require(sid in trusted and mask == 0x1F01FF and not flags & 8
                        and (not directory or flags & 3 == 3), "private_acl")
            else:
                require(sid in trusted or mask & 0x500D0156 == 0, "ancestor_acl")
        if private:
            require(obs["owner_sid"] == self.spec.operator_sid and len(aces) == 3
                    and {a[0] for a in aces} == trusted, "private_acl")
        return obs

    def _open_root(self):
        path = self.spec.volume_path
        parent, token = self._open(None, "\\??\\" + path[4:], ANCESTOR_ACCESS, SHARE_RW)
        obs = self._observe(parent, path, True, private=False)
        self.chain.append((parent, token, path, obs, False))
        for i, name in enumerate(self.spec.components):
            last = i == len(self.spec.components) - 1
            path = path.rstrip("\\") + "\\" + name
            parent, token = self._open(parent, name, ROOT_ACCESS if last else ANCESTOR_ACCESS, SHARE_RW)
            obs = self._observe(parent, path, True, private=last)
            self.chain.append((parent, token, path, obs, last))
        require(obs["file_id"] == self.spec.file_id
                and obs["security_sha256"] == self.spec.security_sha256, "root_identity")
        self.root = parent

    def _recheck(self):
        for handle, _, path, before, private in self.chain:
            after = self._observe(handle, path, True, private=private)
            require(_identity(before) == _identity(after), "integrity_failure")

    def _read(self, handle, expected, cap):
        require(type(expected) is int and 0 < expected <= cap, "stored_size")
        self.op.call(self.api.rewind, handle)
        data = bytearray()
        while len(data) < expected:
            count = min(BLOCK, expected - len(data))
            block = self.op.call(self.api.read, handle, count)
            require(type(block) is bytes and 0 < len(block) <= count, "integrity_failure")
            data.extend(block)
        return bytes(data)

    def _check_bundle(self, handle, path, verify, expected_identity=None, expected_files=None):
        self._recheck()
        obs = self._observe(handle, path, True, private=True)
        if expected_identity is not None:
            require(_identity(obs) == expected_identity, "integrity_failure")
        require(self.op.call(self.api.names, handle, self.op) == ("body.bin", "receipt.json"),
                "integrity_failure")
        data = []
        for name, cap in (("body.bin", MAX_BODY), ("receipt.json", MAX_RECEIPT)):
            child, _ = self._open(handle, name, FILE_READER_ACCESS, SHARE_R, False)
            before = self._observe(child, path + "\\" + name, False, private=True)
            if expected_files is not None:
                require(_identity(before) == expected_files[name], "integrity_failure")
            value = self._read(child, before["length"], cap)
            after = self._observe(child, path + "\\" + name, False, private=True)
            require(_identity(before) == _identity(after) and before["length"] == after["length"],
                    "integrity_failure")
            data.append(value)
        self.op.call(verify, *data)
        self._recheck()
        require(_identity(self._observe(handle, path, True, private=True)) == _identity(obs),
                "integrity_failure")
        # Publish the verification classification before any reader closures.
        # Operation closes readers before their directories, even on cancellation.
        return tuple(data)

    def publish(self, identifier, body, receipt, verify):
        require(type(body) is bytes and 1 <= len(body) <= MAX_BODY and type(receipt) is bytes
                and 1 <= len(receipt) <= MAX_RECEIPT, "stored_size")
        staging, final = bundle_name(identifier, "staging"), bundle_name(identifier, "complete")
        path = self.spec.final_path + "\\" + staging
        self.op.integrity = "INCOMPLETE_STAGING"
        handle, _ = self._open(self.root, staging, SOURCE_ACCESS, SHARE_RW, True, True)
        before = self._observe(handle, path, True, private=True)
        writers = []
        staged_identities = {}
        for name, data in (("body.bin", body), ("receipt.json", receipt)):
            child, token = self._open(handle, name, WRITER_ACCESS, SHARE_R, False, True)
            writers.append(token)
            obs = self._observe(child, path + "\\" + name, False, private=True)
            for offset in range(0, len(data), BLOCK):
                block = data[offset:offset + BLOCK]
                require(self.op.call(self.api.write, child, block) == len(block), "write_count")
            self.op.call(self.api.flush, child)
            require(self._read(child, len(data), len(data)) == data, "integrity_failure")
            after = self._observe(child, path + "\\" + name, False, private=True)
            require(_identity(obs) == _identity(after) and after["length"] == len(data),
                    "integrity_failure")
            staged_identities[name] = _identity(after)
        self.op.call(verify, body, receipt)
        self.op.integrity = "STAGING_VERIFIED"
        for token in reversed(writers):
            self.op.close_one(token)
        require("cleanup_unverified" not in self.op.codes, "cleanup_unverified")
        self._recheck()
        require(_identity(self._observe(handle, path, True, private=True)) == _identity(before),
                "integrity_failure")
        self.op.checkpoint()
        self.op.publication = "RENAME_IN_FLIGHT"
        try:
            status = self.api.rename(handle, self.root, final, self.op)
        except BaseException:
            self.op.publication = "indeterminate"
            raise CustodyError("publication_indeterminate") from None
        classification = classify_status(status)
        # Authoritative outcome recorded BEFORE the cancellation checkpoint.
        if classification == "success":
            self.op.publication = "PUBLISHED_UNVERIFIED"
        elif classification in ("failure", "collision"):
            self.op.publication = "not_published"
            raise CustodyError("publication_collision" if classification == "collision" else "publication_failed")
        else:
            self.op.publication = "indeterminate"
            raise CustodyError("publication_indeterminate")
        if "publication_indeterminate" in self.op.codes:
            self.op.publication = "indeterminate"
            raise CustodyError("publication_indeterminate")
        self.op.checkpoint()
        final_handle, _ = self._open(self.root, final, READER_ACCESS, SHARE_RWD)
        try:
            checked_body, checked_receipt = self._check_bundle(
                final_handle, self.spec.final_path + "\\" + final, verify,
                _identity(before), staged_identities)
            require(checked_body == body and checked_receipt == receipt, "integrity_failure")
        except BaseException as error:
            if getattr(error, "code", None) not in ("cancelled", "deadline"):
                self.op.integrity = "failed"
                self.op.note(CustodyError("integrity_failure"))
            raise
        self.op.publication, self.op.integrity = "PUBLISHED_VERIFIED", "PUBLISHED_VERIFIED"

    def recover(self, identifier, verify):
        final = bundle_name(identifier, "complete")
        handle, _ = self._open(self.root, final, READER_ACCESS, SHARE_RWD)
        self.op.publication = "existing_unverified"
        try:
            result = self._check_bundle(handle, self.spec.final_path + "\\" + final, verify)
        except BaseException as error:
            if getattr(error, "code", None) not in ("cancelled", "deadline"):
                self.op.integrity = "failed"
                self.op.note(CustodyError("integrity_failure"))
            raise
        self.op.publication = "existing_verified_local"
        return result

    def close(self):
        # Every handle belongs to Operation; reverse registration order closes
        # readers, final directory, source, root, ancestors. No duplicate closes.
        if self.op.quarantined:
            raise CustodyError("cleanup_unverified")
        for token in reversed(self.tokens):
            self.op.close_one(token)
        require("cleanup_unverified" not in self.op.codes, "cleanup_unverified")
