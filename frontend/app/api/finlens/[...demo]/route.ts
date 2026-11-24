import replies from "./demo-replies.json";
import { makeDemoHandler } from "./demo-handler.mjs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const handle = makeDemoHandler(replies);
export const GET = handle;
export const POST = handle;
export const HEAD = handle;
export const OPTIONS = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
