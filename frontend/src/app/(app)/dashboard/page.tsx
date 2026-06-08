import { requireSession } from "@/lib/auth/session";
import { getStats } from "@/lib/api/workflow";
import { StatCards } from "@/components/dashboard/stat-cards";
import { TriageChart } from "@/components/dashboard/triage-chart";
import { FlagsChart } from "@/components/dashboard/flags-chart";
import { QuickActions } from "@/components/dashboard/quick-actions";

export const metadata = { title: "Dashboard · Cervical MRI" };

export default async function DashboardPage() {
  const user = await requireSession();
  const stats = await getStats();
  return (
    <div className="mx-auto w-full max-w-6xl space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCards stats={stats} />
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <TriageChart stats={stats} />
        <div className="lg:col-span-2">
          <FlagsChart stats={stats} />
        </div>
      </div>
      <QuickActions role={user.role} />
    </div>
  );
}
