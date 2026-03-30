"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { OrderResponse } from "@/types";

type ColumnType = "new" | "preparing" | "ready";

interface OrderCardProps {
  order: OrderResponse;
  onAdvance: (orderId: string) => void;
  columnType: ColumnType;
}

function timeSince(dateString: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(dateString).getTime()) / 1000
  );
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

const cardStyles: Record<ColumnType, string> = {
  new: "bg-primary/[0.08] border border-primary/15 rounded-xl p-4 animate-slide-in-top",
  preparing: "bg-amber-500/[0.06] border border-amber-500/12 rounded-xl p-4",
  ready: "bg-green-500/[0.06] border border-green-500/12 rounded-xl p-4",
};

const orderNumberStyles: Record<ColumnType, string> = {
  new: "font-bold text-sm text-primary",
  preparing: "font-bold text-sm text-amber-400",
  ready: "font-bold text-sm text-green-400",
};

export function OrderCard({ order, onAdvance, columnType }: OrderCardProps) {
  const handlePrint = (e: React.MouseEvent) => {
    e.stopPropagation();
    const printEl = document.getElementById(`print-receipt-${order.id}`);
    if (!printEl) return;
    printEl.classList.add("print-receipt");
    const cleanup = () => {
      printEl.classList.remove("print-receipt");
      window.removeEventListener("afterprint", cleanup);
    };
    window.addEventListener("afterprint", cleanup);
    window.print();
  };

  return (
    <div className={cardStyles[columnType]}>
      <div className="flex justify-between items-start mb-2">
        <div className="flex items-center gap-2">
          <span className={orderNumberStyles[columnType]}>
            #{order.id.slice(0, 8)}
          </span>
          {order.table_identifier && (
            <span className="text-muted-foreground text-xs">
              Table {order.table_identifier}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handlePrint}
            className="text-xs h-auto py-0.5 px-2"
          >
            Print
          </Button>
          <span className="text-xs text-muted-foreground">
            {timeSince(order.created_at)}
          </span>
        </div>
      </div>

      {order.customer_allergies?.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {order.customer_allergies.map((allergy) => (
            <Badge key={allergy} variant="destructive" className="text-xs">
              {allergy}
            </Badge>
          ))}
        </div>
      )}

      <ul className="text-sm space-y-1 mb-3">
        {order.items.map((item) => (
          <li key={item.id}>
            <span className="text-foreground">
              {item.quantity}x {item.name}
            </span>
            <span className="text-muted-foreground text-xs">
              {" "}({item.variant_label})
            </span>
            {item.modifiers && item.modifiers.length > 0 && (
              <ul className="ml-4 mt-0.5 space-y-0.5">
                {item.modifiers.map((mod) => (
                  <li key={mod.id} className="text-xs text-muted-foreground">
                    + {mod.name}
                  </li>
                ))}
              </ul>
            )}
            {item.special_requests && (
              <div className="ml-4 text-xs text-muted-foreground italic">
                Note: {item.special_requests}
              </div>
            )}
          </li>
        ))}
      </ul>

      <div className="flex items-center justify-between">
        <span className="text-muted-foreground text-xs">
          {order.table_identifier ? `Table ${order.table_identifier}` : "No table"} · {timeSince(order.created_at)}
        </span>
        {columnType === "new" && (
          <Button
            variant="gradient"
            size="sm"
            onClick={() => onAdvance(order.id)}
          >
            Start Preparing
          </Button>
        )}
        {columnType === "preparing" && (
          <button
            className="bg-amber-500/15 border border-amber-500/25 text-amber-400 rounded-lg hover:bg-amber-500/25 px-3 py-1.5 text-sm font-medium transition-colors"
            onClick={() => onAdvance(order.id)}
          >
            Mark Ready
          </button>
        )}
        {columnType === "ready" && (
          <button
            className="bg-green-500/15 border border-green-500/25 text-green-400 rounded-lg hover:bg-green-500/25 px-3 py-1.5 text-sm font-medium transition-colors"
            onClick={() => onAdvance(order.id)}
          >
            Complete
          </button>
        )}
      </div>

      {/* Hidden receipt template — only visible during printing */}
      <div id={`print-receipt-${order.id}`} style={{ display: "none" }}>
        <div style={{ textAlign: "center", fontWeight: "bold" }}>
          ORDER #{order.id.slice(0, 8)}
        </div>
        {order.table_identifier && <div>Table: {order.table_identifier}</div>}
        <div>Time: {new Date(order.created_at).toLocaleTimeString()}</div>
        <hr />
        {order.items.map((item) => (
          <div key={item.id}>
            {item.quantity}x {item.name} ({item.variant_label})
            {item.modifiers?.map((mod) => (
              <div key={mod.id}>  + {mod.name}</div>
            ))}
            {item.special_requests && <div>  Note: {item.special_requests}</div>}
          </div>
        ))}
        {order.customer_allergies?.length > 0 && (
          <>
            <hr />
            <div>ALLERGIES: {order.customer_allergies.join(", ")}</div>
          </>
        )}
        <hr />
        <div>
          Payment: {order.payment_status === "pos_collected"
            ? "Pay at counter"
            : "Paid online"}
        </div>
      </div>
    </div>
  );
}
