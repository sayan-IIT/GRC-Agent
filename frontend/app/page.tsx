import Link from "next/link";
import { ClipboardList, FileCheck2, KeyRound, ShieldAlert } from "lucide-react";

const solutions = [
  {
    title: "Identity & Access Risk",
    description: "Access posture, privilege drift, joiner-mover-leaver exceptions, and account control review.",
    href: "#",
    icon: KeyRound,
    status: "Preview",
  },
  {
    title: "TPRM/ Risk Intelligence Scan",
    description: "Live CrustData ingestion, AI scoring agents, human review, and vendor-risk decisioning.",
    href: "/risk-intelligence",
    icon: ShieldAlert,
    status: "Open demo",
  },
  {
    title: "IT & Cyber Risk",
    description: "Control gaps, cyber exposure, security incidents, and technology risk prioritization.",
    href: "#",
    icon: ClipboardList,
    status: "Preview",
  },
  {
    title: "Audit Log Generation & Compliance",
    description: "Evidence capture, reviewer decisions, audit narratives, and compliance-ready records.",
    href: "#",
    icon: FileCheck2,
    status: "Preview",
  },
];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-[#f7f8f4]">
      <section className="border-b border-[#d9ded2] bg-white">
        <div className="mx-auto max-w-7xl px-6 py-8">
          <div className="mb-3 inline-flex rounded border border-moss/25 bg-mint px-3 py-1 text-sm font-semibold text-moss">
            AI GRC Risk Intelligence Platform
          </div>
          <h1 className="max-w-4xl text-3xl font-semibold text-ink md:text-5xl">Solution Console</h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-[#546259]">
            Select a risk workflow to demo. The TPRM scan is wired to live CrustData ingestion, AI scoring, and human approval.
          </p>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-5 px-6 py-8 md:grid-cols-2">
        {solutions.map((solution) => {
          const Icon = solution.icon;
          const enabled = solution.href !== "#";
          const content = (
            <div className="h-full rounded border border-[#d9ded2] bg-white p-6 hover:border-moss/50">
              <div className="mb-5 flex items-start justify-between gap-4">
                <div className="inline-flex h-11 w-11 items-center justify-center rounded border border-[#d9ded2] bg-[#eef3ea] text-moss">
                  <Icon size={22} />
                </div>
                <span className="rounded border border-[#d9ded2] px-3 py-1 text-xs font-semibold text-[#546259]">{solution.status}</span>
              </div>
              <h2 className="text-xl font-semibold text-ink">{solution.title}</h2>
              <p className="mt-3 text-sm leading-6 text-[#546259]">{solution.description}</p>
            </div>
          );

          return enabled ? (
            <Link key={solution.title} href={solution.href} className="block">
              {content}
            </Link>
          ) : (
            <div key={solution.title} className="opacity-80">
              {content}
            </div>
          );
        })}
      </section>
    </main>
  );
}

