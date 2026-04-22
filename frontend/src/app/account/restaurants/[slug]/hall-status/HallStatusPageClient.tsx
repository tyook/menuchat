"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { useRequireRestaurantAccess } from "@/hooks/use-auth";
import { useHallStatus } from "@/hooks/use-hall-status";
import type { HallStatusTable, HallStatusOrder } from "@/types";

function timeElapsed(dateString: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(dateString).getTime()) / 1000
  );
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainingMin = minutes % 60;
  return `${hours}h ${remainingMin}m`;
}

function OrderDetailModal({
  table,
  onClose,
}: {
  table: HallStatusTable;
  onClose: () => void;
}) {
  if (!table.tab) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-card border border-border rounded-2xl p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-bold">
            {table.name} ({table.number})
          </h2>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground text-xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="flex justify-between items-center mb-4 text-sm">
          <span className="text-muted-foreground">
            Tab opened{" "}
            {table.tab.first_order_at
              ? timeElapsed(table.tab.first_order_at)
              : timeElapsed(table.tab.opened_at)}{" "}
            ago
          </span>
          <span className="font-bold text-lg">${table.tab.total}</span>
        </div>

        <div className="space-y-3">
          {table.tab.orders.map((order: HallStatusOrder, idx: number) => (
            <div
              key={order.id}
              className="border border-border rounded-xl p-3"
            >
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium">
                  Order {idx + 1}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    {timeElapsed(order.created_at)} ago
                  </span>
                  <span className="text-sm font-semibold">
                    ${order.total_price}
                  </span>
                </div>
              </div>
              <ul className="text-sm text-muted-foreground space-y-0.5">
                {order.items.map((item) => (
                  <li key={item.id}>
                    {item.quantity}x {item.name}{" "}
                    <span className="text-xs">({item.variant_label})</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TableCard({
  table,
  onViewDetail,
}: {
  table: HallStatusTable;
  onViewDetail: () => void;
}) {
  const hasOrders = table.has_tab && table.tab !== null;

  const bgClass = hasOrders
    ? "bg-amber-500/[0.08] border-amber-500/20 hover:border-amber-500/40"
    : "bg-green-500/[0.08] border-green-500/20 hover:border-green-500/40";

  const statusText = hasOrders ? "Occupied" : "Empty";
  const statusClass = hasOrders
    ? "bg-amber-500/15 text-amber-400"
    : "bg-green-500/15 text-green-400";

  return (
    <Card
      className={`border rounded-2xl p-4 transition-colors ${bgClass} ${
        hasOrders ? "cursor-pointer" : ""
      }`}
      onClick={hasOrders ? onViewDetail : undefined}
    >
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="font-semibold text-foreground">{table.name}</h3>
          <p className="text-xs text-muted-foreground">#{table.number}</p>
        </div>
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusClass}`}
        >
          {statusText}
        </span>
      </div>

      {hasOrders && table.tab ? (
        <>
          <div className="text-xs text-muted-foreground mb-2">
            {table.tab.first_order_at
              ? timeElapsed(table.tab.first_order_at)
              : timeElapsed(table.tab.opened_at)}{" "}
            elapsed
          </div>
          <div className="flex justify-between items-center">
            <span className="text-xs text-muted-foreground">
              {table.tab.order_count} order
              {table.tab.order_count !== 1 ? "s" : ""}
            </span>
            <span className="font-bold text-foreground">
              ${table.tab.total}
            </span>
          </div>
        </>
      ) : (
        <div className="text-sm text-green-400 mt-1">Available</div>
      )}
    </Card>
  );
}

export default function HallStatusPageClient() {
  const params = useParams();
  const slug = params.slug as string;
  const isAuthenticated = useRequireRestaurantAccess();
  const { data: tables, isLoading, error } = useHallStatus(slug);
  const [selectedTable, setSelectedTable] = useState<HallStatusTable | null>(
    null
  );

  if (isAuthenticated === null || isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (isAuthenticated === false) {
    return null;
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background p-6">
        <div className="max-w-4xl mx-auto text-center py-12">
          <p className="text-destructive">Failed to load hall status.</p>
          <p className="text-sm text-muted-foreground mt-2">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </div>
      </div>
    );
  }

  const occupiedCount = tables?.filter((t) => t.has_tab).length ?? 0;
  const totalCount = tables?.length ?? 0;

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-5xl mx-auto">
        <Link
          href="/account/restaurants"
          className="text-sm text-muted-foreground hover:underline"
        >
          Back to dashboard
        </Link>
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Hall Status</h1>
          <span className="text-sm text-muted-foreground">
            {occupiedCount} / {totalCount} occupied
          </span>
        </div>

        {tables && tables.length > 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {tables.map((table) => (
              <TableCard
                key={table.id}
                table={table}
                onViewDetail={() => setSelectedTable(table)}
              />
            ))}
          </div>
        ) : (
          <p className="text-center text-muted-foreground py-12">
            No tables configured. Add tables in Settings to use Hall Status.
          </p>
        )}
      </div>

      {selectedTable && (
        <OrderDetailModal
          table={selectedTable}
          onClose={() => setSelectedTable(null)}
        />
      )}
    </div>
  );
}
