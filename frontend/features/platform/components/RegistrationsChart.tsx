"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatDate } from "@/lib/format";

type Point = { date: string; count: number };

/** Loosely typed on purpose: works across recharts major versions. */
function ChartTooltip({ active, payload }: { active?: boolean; payload?: ReadonlyArray<{ payload?: Point }> }) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return (
    <div className="rounded-md border bg-card px-2 py-1 text-xs text-card-foreground shadow">
      <div className="font-medium">{formatDate(point.date)}</div>
      <div>
        {point.count} new {point.count === 1 ? "school" : "schools"}
      </div>
    </div>
  );
}

export function RegistrationsChart({ data }: { data: Point[] }) {
  return (
    <div className="h-64 w-full text-muted-foreground" role="img" aria-label="New school registrations over the last 30 days">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid vertical={false} stroke="currentColor" strokeOpacity={0.15} />
          <XAxis
            dataKey="date"
            tickFormatter={(value: string) => value.slice(8)}
            tick={{ fill: "currentColor", fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            interval={2}
          />
          <YAxis allowDecimals={false} tick={{ fill: "currentColor", fontSize: 12 }} tickLine={false} axisLine={false} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "currentColor", fillOpacity: 0.08 }} />
          <Bar dataKey="count" className="fill-primary" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
