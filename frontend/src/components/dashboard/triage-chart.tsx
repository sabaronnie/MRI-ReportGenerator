"use client";

import { Cell, Label, Pie, PieChart } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { Stats } from "@/lib/api/workflow";

const CONFIG = {
  urgent: { label: "Urgent", color: "#e11d48" },
  review: { label: "Review", color: "#d97706" },
  none: { label: "No flags", color: "#0f766e" },
} satisfies ChartConfig;

export function TriageChart({ stats }: { stats: Stats }) {
  const data = (["urgent", "review", "none"] as const)
    .map((k) => ({ key: k, label: CONFIG[k].label, value: stats.by_triage[k] ?? 0, fill: CONFIG[k].color }))
    .filter((d) => d.value > 0);
  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle>Triage mix</CardTitle>
        <CardDescription>Auto-screen outcome across all cases</CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        {total === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">No cases yet.</p>
        ) : (
          <ChartContainer config={CONFIG} className="mx-auto aspect-square max-h-[220px]">
            <PieChart>
              <ChartTooltip content={<ChartTooltipContent nameKey="label" hideLabel />} />
              <Pie data={data} dataKey="value" nameKey="label" innerRadius={58} strokeWidth={4}>
                {data.map((d) => (
                  <Cell key={d.key} fill={d.fill} />
                ))}
                <Label
                  content={({ viewBox }) =>
                    viewBox && "cx" in viewBox ? (
                      <text x={viewBox.cx} y={viewBox.cy} textAnchor="middle" dominantBaseline="middle">
                        <tspan x={viewBox.cx} y={viewBox.cy} className="fill-foreground text-2xl font-semibold">
                          {total}
                        </tspan>
                        <tspan x={viewBox.cx} y={(viewBox.cy ?? 0) + 18} className="fill-muted-foreground text-xs">
                          cases
                        </tspan>
                      </text>
                    ) : null
                  }
                />
              </Pie>
            </PieChart>
          </ChartContainer>
        )}
        <div className="mt-3 flex flex-wrap justify-center gap-3">
          {data.map((d) => (
            <span key={d.key} className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="size-2 rounded-full" style={{ background: d.fill }} />
              {d.label} · {d.value}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
