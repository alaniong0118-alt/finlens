import Link from "next/link";
import {notFound} from "next/navigation";
import {HypotheticalRisk} from "../../components/hypothetical-risk";

export const dynamic = "force-dynamic";
export default function HypotheticalRiskPage() {
  if (process.env.FINLENS_HYPOTHETICAL_RISK_UI !== "1") notFound();
  return <><nav className="workspace" aria-label="Risk Lab workflows" style={{paddingBottom:0}}><Link href="/hypothetical-risk/stress">Hypothetical linear price stress</Link></nav><HypotheticalRisk /></>;
}
