import {notFound} from "next/navigation";
import {HypotheticalRisk} from "../../components/hypothetical-risk";

export const dynamic = "force-dynamic";
export default function HypotheticalRiskPage() {
  if (process.env.FINLENS_HYPOTHETICAL_RISK_UI !== "1") notFound();
  return <HypotheticalRisk />;
}
