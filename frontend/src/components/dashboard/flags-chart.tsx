"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { Stats } from "@/lib/api/workflow";

const CONFIG = { count: { label: "Flagged findings", color: "#0f766e" } } satisfies ChartConfig;

export function FlagsChart({ stats }: { stats: Stats }) {
  const data = Object.entries(stats.flags_by_group)
    .map(([group, count]) => ({ group, count }))
    .sort((a, b) => b.count - a.count);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Flagged findings by group</CardTitle>
        <CardDescription>Outside-reference findings across all cases</CardDescription>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            No findings flagged for review.
          </p>
        ) : (
          <ChartContainer config={CONFIG} className="h-[220px] w-full">
            <BarChart accessibilityLayer data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
              <CartesianGrid horizontal={false} />
              <YAxis type="category" dataKey="group" tickLine={false} axisLine={false} width={92} />
              <XAxis type="number" hide allowDecimals={false} />
              <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel />} />
              <Bar dataKey="count" fill="var(--color-count)" radius={5} />
            </BarChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
