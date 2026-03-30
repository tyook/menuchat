"use client";

import { OrderCard } from "./OrderCard";
import type { OrderResponse } from "@/types";

type ColumnType = "new" | "preparing" | "ready";

interface OrderColumnProps {
  title: string;
  orders: OrderResponse[];
  onAdvance: (orderId: string) => void;
  columnType: ColumnType;
}

const countBadgeStyles: Record<ColumnType, string> = {
  new: "bg-primary/20 text-primary",
  preparing: "bg-amber-500/20 text-amber-400",
  ready: "bg-green-500/20 text-green-400",
};

export function OrderColumn({
  title,
  orders,
  onAdvance,
  columnType,
}: OrderColumnProps) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="font-semibold text-xs uppercase tracking-wider text-muted-foreground">
          {title}
        </h2>
        <span
          className={`inline-flex items-center justify-center rounded-full px-2 py-0.5 text-xs font-semibold ${countBadgeStyles[columnType]}`}
        >
          {orders.length}
        </span>
      </div>
      <div className="space-y-3">
        {orders.map((order) => (
          <OrderCard
            key={order.id}
            order={order}
            onAdvance={onAdvance}
            columnType={columnType}
          />
        ))}
        {orders.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">
            No orders
          </p>
        )}
      </div>
    </div>
  );
}
