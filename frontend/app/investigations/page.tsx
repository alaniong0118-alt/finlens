import PrivateWorkspace from "@/components/private-workspace";
import Link from "next/link";

export default function Investigations() {
  return <main className="workspace"><Link href="/">Back to public research</Link><PrivateWorkspace /></main>;
}
