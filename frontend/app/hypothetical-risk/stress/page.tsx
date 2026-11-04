import Link from "next/link";
import {notFound} from "next/navigation";
import {HypotheticalStress} from "../../../components/hypothetical-stress";
export const dynamic="force-dynamic";
export default function HypotheticalStressPage() {
  if(process.env.FINLENS_HYPOTHETICAL_RISK_UI!=="1") notFound();
  return <><nav className="workspace" aria-label="Risk Lab workflows" style={{paddingBottom:0}}><Link href="/hypothetical-risk">Historical hypothetical risk</Link></nav><HypotheticalStress/></>;
}
