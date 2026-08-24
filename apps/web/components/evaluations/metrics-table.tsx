"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatPercent } from "@/lib/format";

export type EvaluationMetric = {
  label: string;
  shortLabel: string;
  value: number | null | undefined;
};

export function MetricsTable({ metrics }: { metrics: EvaluationMetric[] }) {
  const chartData = metrics.flatMap((metric) => metric.value == null ? [] : [{ name: metric.shortLabel, value: metric.value }]);
  return (
    <section className="panel overflow-hidden" aria-labelledby="metrics-heading">
      <header className="border-b border-border px-5 py-4 sm:px-6"><h2 className="font-heading text-lg font-semibold" id="metrics-heading">Measured quality and safety</h2><p className="mt-1 text-sm text-muted-foreground">The chart is decorative; the complete measured values are available in the table below.</p></header>
      {chartData.length ? (
        <div aria-hidden className="h-64 p-4 sm:p-6">
          <ResponsiveContainer height="100%" width="100%">
            <BarChart data={chartData} margin={{ top: 4, right: 4, left: -16, bottom: 4 }}>
              <CartesianGrid stroke="#dbe3ec" strokeDasharray="3 3" vertical={false} />
              <XAxis axisLine={false} dataKey="name" fontSize={11} interval={0} tickLine={false} />
              <YAxis axisLine={false} domain={[0, 1]} fontSize={11} tickFormatter={(value: number) => `${Math.round(value * 100)}%`} tickLine={false} />
              <Tooltip formatter={(value) => formatPercent(Number(value))} />
              <Bar dataKey="value" fill="#087e72" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : null}
      <div className="overflow-x-auto border-t border-border">
        <table className="w-full min-w-[32rem] text-left text-sm">
          <caption className="sr-only">Measured evaluation metrics</caption>
          <thead className="bg-surface-raised text-xs font-semibold tracking-wide text-muted-foreground uppercase"><tr><th className="px-5 py-3" scope="col">Metric</th><th className="px-5 py-3 text-right" scope="col">Measured value</th></tr></thead>
          <tbody className="divide-y divide-border">{metrics.map((metric) => <tr key={metric.label}><th className="px-5 py-3 font-medium" scope="row">{metric.label}</th><td className="tabular-nums px-5 py-3 text-right font-semibold">{metric.value == null ? "Not measured" : formatPercent(metric.value)}</td></tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}
