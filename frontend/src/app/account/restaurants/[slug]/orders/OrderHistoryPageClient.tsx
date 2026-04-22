"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { useRequireRestaurantAccess } from "@/hooks/use-auth";
import { useRestaurantOrders } from "@/hooks/use-restaurant-orders";

const statusClass: Record<string, string> = {
  pending_payment: "bg-destructive/10 text-destructive",
  pending: "bg-primary/10 text-primary",
  confirmed: "bg-primary/10 text-primary",
  preparing: "bg-warning/10 text-warning",
  ready: "bg-success/10 text-success",
  completed: "bg-success/10 text-success",
};

export default function OrderHistoryPage() {
  const params = useParams();
  const slug = params.slug as string;
  const isAuthenticated = useRequireRestaurantAccess();
  const { data: orders, isLoading, error } = useRestaurantOrders(slug);

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
          <p className="text-destructive">Failed to load orders.</p>
          <p className="text-sm text-muted-foreground mt-2">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto">
        <Link
          href="/account/restaurants"
          className="text-sm text-muted-foreground hover:underline"
        >
          Back to dashboard
        </Link>
        <h1 className="text-2xl font-bold mb-6">Order History</h1>

        <div className="space-y-3">
          {orders && orders.length > 0 ? (
            orders.map((order) => (
              <Card key={order.id} className="bg-card border border-border rounded-2xl p-4 hover:bg-muted/50 transition-colors">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="font-mono text-sm">
                      #{order.id.slice(0, 8)}
                    </span>
                    {order.table_identifier && (
                      <span className="text-sm text-muted-foreground ml-2">
                        Table {order.table_identifier}
                      </span>
                    )}
                    <p className="text-xs text-muted-foreground mt-1">
                      {new Date(order.created_at).toLocaleDateString("en-US", {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusClass[order.status] || "bg-muted text-muted-foreground"}`}>
                      {order.status}
                    </span>
                    <span className="font-semibold">${order.total_price}</span>
                  </div>
                </div>
                <ul className="text-sm mt-2 text-muted-foreground">
                  {order.items.map((item) => (
                    <li key={item.id}>
                      {item.quantity}x {item.name} ({item.variant_label})
                      {item.modifiers && item.modifiers.length > 0 && (
                        <ul className="ml-4">
                          {item.modifiers.map((m) => (
                            <li key={m.id} className="text-xs">
                              + {m.name} (+${m.price_adjustment})
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  ))}
                </ul>
              </Card>
            ))
          ) : (
            <p className="text-center text-muted-foreground py-12">
              No orders yet. Orders will appear here once customers start
              ordering.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
