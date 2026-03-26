"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { OrderResponse } from "@/types";

interface OrderCardProps {
  order: OrderResponse;
  onAdvance: (orderId: string) => void;
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

const statusLabels: Record<string, string> = {
  confirmed: "Start Preparing",
  preparing: "Mark Ready",
  ready: "Complete",
};

export function OrderCard({ order, onAdvance }: OrderCardProps) {
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
    <Card
      className="p-4 cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => onAdvance(order.id)}
    >
      <div className="flex justify-between items-start mb-2">
        <div>
          <span className="font-bold text-sm">
            #{order.id.slice(0, 8)}
          </span>
          {order.table_identifier && (
            <Badge variant="outline" className="ml-2">
              Table {order.table_identifier}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handlePrint}
            className="text-xs"
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
            {item.quantity}x {item.name} ({item.variant_label})
            {item.special_requests && (
              <span className="text-muted-foreground italic">
                {" "}- {item.special_requests}
              </span>
            )}
          </li>
        ))}
      </ul>

      <div className="text-xs text-center text-primary font-medium">
        Tap to {statusLabels[order.status] || "update"}
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
    </Card>
  );
}
