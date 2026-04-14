"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { format } from "date-fns";
import { CalendarIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useRequireRestaurantAccess } from "@/hooks/use-auth";
import { useAnalytics } from "@/hooks/use-analytics";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";
import type { PeakHour } from "@/types";

const PERIODS = [
  { label: "7 days", value: "7d" },
  { label: "30 days", value: "30d" },
  { label: "90 days", value: "90d" },
  { label: "Custom", value: "custom" },
] as const;

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatPercent(current: number, previous: number): string | null {
  if (previous === 0) return current > 0 ? "+100%" : null;
  const change = ((current - previous) / previous) * 100;
  const sign = change >= 0 ? "+" : "";
  return `${sign}${change.toFixed(1)}%`;
}

function formatHour(hour: number): string {
  if (hour === 0) return "12a";
  if (hour === 12) return "12p";
  return hour < 12 ? `${hour}a` : `${hour - 12}p`;
}

function TrendBadge({ current, previous }: { current: number; previous: number }) {
  const pct = formatPercent(current, previous);
  if (!pct) return null;
  const isPositive = current >= previous;
  return (
    <span
      className={`text-xs font-medium px-1.5 py-0.5 rounded ${
        isPositive
          ? "bg-success/10 text-success"
          : "bg-destructive/10 text-destructive"
      }`}
    >
      {pct}
    </span>
  );
}

function StatCard({
  label,
  value,
  trend,
}: {
  label: string;
  value: string;
  trend?: React.ReactNode;
}) {
  return (
    <Card className="bg-card border border-border rounded-2xl p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {trend && <div className="mt-1">{trend}</div>}
    </Card>
  );
}

function HeatmapBar({ hours }: { hours: PeakHour[] }) {
  const max = Math.max(...hours.map((h) => h.orders), 1);
  return (
    <div className="flex gap-0.5 items-end h-24">
      {hours.map((h) => {
        const intensity = h.orders / max;
        return (
          <div key={h.hour} className="flex-1 flex flex-col items-center gap-1">
            <div
              className="w-full rounded-sm transition-all"
              style={{
                height: `${Math.max(intensity * 100, 4)}%`,
                backgroundColor:
                  intensity > 0.75
                    ? "hsl(var(--primary))"
                    : intensity > 0.4
                      ? "hsl(var(--primary) / 0.6)"
                      : intensity > 0
                        ? "hsl(var(--primary) / 0.25)"
                        : "hsl(var(--muted))",
              }}
              title={`${formatHour(h.hour)}: ${h.orders} orders`}
            />
            {h.hour % 4 === 0 && (
              <span className="text-[10px] text-muted-foreground">
                {formatHour(h.hour)}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

const PAYMENT_LABELS: Record<string, string> = {
  paid: "Stripe Online",
  pos_collected: "POS Collected",
  pending: "Pending",
  failed: "Failed",
  refunded: "Refunded",
};

export default function AnalyticsPage() {
  const params = useParams();
  const slug = params.slug as string;
  const isAuthenticated = useRequireRestaurantAccess();
  const [period, setPeriod] = useState("30d");
  const [rangeFrom, setRangeFrom] = useState<Date | undefined>();
  const [rangeTo, setRangeTo] = useState<Date | undefined>();
  const [calendarOpen, setCalendarOpen] = useState(false);

  const startDate = rangeFrom ? format(rangeFrom, "yyyy-MM-dd") : undefined;
  const endDate = rangeTo ? format(rangeTo, "yyyy-MM-dd") : undefined;

  const { data, isLoading, error } = useAnalytics(
    slug,
    period,
    startDate,
    endDate
  );

  // Wait for custom date range before showing loading
  const isWaitingForDates =
    period === "custom" && (!startDate || !endDate);

  if (isAuthenticated === null || (isLoading && !isWaitingForDates && !data)) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (isAuthenticated === false) {
    return null;
  }

  const summary = data?.summary;
  const daily_orders = data?.daily_orders ?? [];
  const top_items = data?.top_items ?? [];
  const peak_hours = data?.peak_hours ?? [];
  const payment_breakdown = data?.payment_breakdown ?? [];

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-5xl mx-auto">
        <Link
          href="/account/restaurants"
          className="text-sm text-muted-foreground hover:underline"
        >
          Back to dashboard
        </Link>

        <div className="flex items-center justify-between mt-2 mb-6 flex-wrap gap-2">
          <h1 className="text-2xl font-bold">Analytics</h1>
          <div className="flex items-center gap-2">
            <div className="flex gap-1 bg-muted rounded-lg p-1">
              {PERIODS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => {
                    setPeriod(p.value);
                    if (p.value === "custom") {
                      setCalendarOpen(true);
                    }
                  }}
                  className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                    period === p.value
                      ? "bg-background text-foreground font-medium shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            {period === "custom" && (
              <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-sm font-normal"
                  >
                    <CalendarIcon className="mr-1.5 h-4 w-4" />
                    {rangeFrom ? (
                      rangeTo ? (
                        <>
                          {format(rangeFrom, "MMM d, yyyy")} –{" "}
                          {format(rangeTo, "MMM d, yyyy")}
                        </>
                      ) : (
                        <>{format(rangeFrom, "MMM d, yyyy")} – ?</>
                      )
                    ) : (
                      "Pick dates"
                    )}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="end">
                  <Calendar
                    mode="range"
                    selected={
                      rangeFrom
                        ? { from: rangeFrom, to: rangeTo }
                        : undefined
                    }
                    onSelect={(range) => {
                      if (!rangeFrom || rangeTo) {
                        // First click (or resetting after a completed selection)
                        setRangeFrom(range?.from);
                        setRangeTo(undefined);
                      } else {
                        // Second click — set end date
                        const picked = range?.to ?? range?.from;
                        if (picked) {
                          if (picked < rangeFrom) {
                            setRangeFrom(picked);
                            setRangeTo(rangeFrom);
                          } else {
                            setRangeTo(picked);
                          }
                          setCalendarOpen(false);
                        }
                      }
                    }}
                    numberOfMonths={2}
                    disabled={{ after: new Date() }}
                  />
                </PopoverContent>
              </Popover>
            )}
          </div>
        </div>

        {error ? (
          <div className="text-center py-12">
            <p className="text-destructive">Failed to load analytics.</p>
            <p className="text-sm text-muted-foreground mt-2">
              {error instanceof Error ? error.message : "Unknown error"}
            </p>
          </div>
        ) : isWaitingForDates ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground">
              Select a date range to view analytics.
            </p>
          </div>
        ) : isLoading || !summary ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        ) : (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <StatCard
                label="Orders"
                value={summary.order_count.toLocaleString()}
                trend={
                  <TrendBadge
                    current={summary.order_count}
                    previous={summary.prev_order_count}
                  />
                }
              />
              <StatCard
                label="Revenue"
                value={formatCurrency(summary.total_revenue)}
                trend={
                  <TrendBadge
                    current={summary.total_revenue}
                    previous={summary.prev_total_revenue}
                  />
                }
              />
              <StatCard
                label="Net Revenue"
                value={formatCurrency(summary.net_revenue)}
              />
              <StatCard
                label="Avg Order"
                value={formatCurrency(summary.avg_order_value)}
              />
            </div>

            {/* Order volume chart */}
            <Card className="bg-card border border-border rounded-2xl p-5 mb-6">
              <h2 className="text-lg font-semibold mb-4">Order Volume</h2>
              {daily_orders.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={daily_orders}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
                      tickFormatter={(d) =>
                        new Date(d).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        })
                      }
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(var(--card))",
                        border: "1px solid hsl(var(--border))",
                        borderRadius: "8px",
                        fontSize: 13,
                      }}
                      labelFormatter={(d) =>
                        new Date(String(d)).toLocaleDateString("en-US", {
                          weekday: "short",
                          month: "short",
                          day: "numeric",
                        })
                      }
                      formatter={(value, name) => [
                        name === "revenue" ? formatCurrency(Number(value)) : value,
                        name === "revenue" ? "Revenue" : "Orders",
                      ]}
                    />
                    <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-center text-muted-foreground py-12">
                  No order data for this period.
                </p>
              )}
            </Card>

            {/* Revenue trend */}
            {daily_orders.length > 0 && (
              <Card className="bg-card border border-border rounded-2xl p-5 mb-6">
                <h2 className="text-lg font-semibold mb-4">Revenue Trend</h2>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={daily_orders}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
                      tickFormatter={(d) =>
                        new Date(d).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        })
                      }
                    />
                    <YAxis
                      tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
                      tickFormatter={(v) => `$${v}`}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(var(--card))",
                        border: "1px solid hsl(var(--border))",
                        borderRadius: "8px",
                        fontSize: 13,
                      }}
                      labelFormatter={(d) =>
                        new Date(String(d)).toLocaleDateString("en-US", {
                          weekday: "short",
                          month: "short",
                          day: "numeric",
                        })
                      }
                      formatter={(value) => [formatCurrency(Number(value)), "Revenue"]}
                    />
                    <Line
                      type="monotone"
                      dataKey="revenue"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            )}

            <div className="grid md:grid-cols-2 gap-6 mb-6">
              {/* Top items */}
              <Card className="bg-card border border-border rounded-2xl p-5">
                <h2 className="text-lg font-semibold mb-4">Top Items</h2>
                {top_items.length > 0 ? (
                  <ol className="space-y-3">
                    {top_items.map((item, i) => {
                      const maxQty = top_items[0].quantity;
                      return (
                        <li key={item.name} className="flex items-center gap-3">
                          <span className="text-sm font-medium text-muted-foreground w-5 text-right">
                            {i + 1}.
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{item.name}</p>
                            <div className="mt-1 h-1.5 bg-muted rounded-full overflow-hidden">
                              <div
                                className="h-full bg-primary rounded-full transition-all"
                                style={{ width: `${(item.quantity / maxQty) * 100}%` }}
                              />
                            </div>
                          </div>
                          <span className="text-sm font-semibold tabular-nums">
                            {item.quantity}
                          </span>
                        </li>
                      );
                    })}
                  </ol>
                ) : (
                  <p className="text-center text-muted-foreground py-8">No item data.</p>
                )}
              </Card>

              {/* Peak hours + payment breakdown */}
              <div className="space-y-6">
                <Card className="bg-card border border-border rounded-2xl p-5">
                  <h2 className="text-lg font-semibold mb-4">Peak Hours</h2>
                  <HeatmapBar hours={peak_hours} />
                </Card>

                <Card className="bg-card border border-border rounded-2xl p-5">
                  <h2 className="text-lg font-semibold mb-3">Payment Types</h2>
                  {payment_breakdown.length > 0 ? (
                    <div className="space-y-2">
                      {payment_breakdown.map((entry) => (
                        <div key={entry.type} className="flex justify-between items-center">
                          <span className="text-sm text-muted-foreground">
                            {PAYMENT_LABELS[entry.type] || entry.type}
                          </span>
                          <span className="text-sm font-semibold tabular-nums">
                            {entry.count}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-center text-muted-foreground py-4">
                      No payment data.
                    </p>
                  )}
                </Card>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
