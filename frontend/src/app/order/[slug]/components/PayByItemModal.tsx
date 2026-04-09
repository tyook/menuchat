"use client";

import { useState } from "react";
import { useOrderStore } from "@/stores/order-store";
import { createTabPayment } from "@/lib/api";

interface PayByItemModalProps {
  slug: string;
  onClose: () => void;
}

export default function PayByItemModal({ slug, onClose }: PayByItemModalProps) {
  const { tabId, tabOrders } = useOrderStore();
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);

  const allItems = tabOrders.flatMap((order) =>
    order.items.map((item) => ({ ...item, orderId: order.id }))
  );

  const toggleItem = (itemId: number) => {
    const next = new Set(selectedItems);
    if (next.has(itemId)) {
      next.delete(itemId);
    } else {
      next.add(itemId);
    }
    setSelectedItems(next);
  };

  const selectedTotal = allItems
    .filter((item) => selectedItems.has(item.id))
    .reduce((sum, item) => sum + parseFloat(item.line_total), 0)
    .toFixed(2);

  const handlePay = async () => {
    if (!tabId || selectedItems.size === 0) return;
    setLoading(true);
    try {
      const { client_secret, payment_id } = await createTabPayment(
        slug,
        tabId,
        "pay_by_item",
        undefined,
        Array.from(selectedItems)
      );
      useOrderStore.getState().setClientSecret(client_secret);
      useOrderStore.getState().setTabPaymentId(payment_id);
      useOrderStore.getState().setStep("payment");
      onClose();
    } catch {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60">
      <div className="max-h-[80vh] w-full max-w-md overflow-y-auto rounded-t-2xl bg-zinc-900 p-6">
        <h3 className="mb-4 text-lg font-bold text-white">Select Your Items</h3>

        <div className="mb-4 flex flex-col gap-2">
          {allItems.map((item) => (
            <label
              key={item.id}
              className="flex cursor-pointer items-center gap-3 rounded-lg bg-zinc-800 p-3"
            >
              <input
                type="checkbox"
                checked={selectedItems.has(item.id)}
                onChange={() => toggleItem(item.id)}
                className="h-5 w-5 rounded border-zinc-600"
              />
              <span className="flex-1 text-sm text-zinc-200">
                {item.quantity}x {item.name}
              </span>
              <span className="text-sm text-zinc-300">${item.line_total}</span>
            </label>
          ))}
        </div>

        <div className="mb-4 rounded-lg bg-zinc-800 p-4 text-center">
          <div className="text-sm text-zinc-400">Your total</div>
          <div className="text-2xl font-bold text-white">${selectedTotal}</div>
        </div>

        <button
          onClick={handlePay}
          disabled={loading || selectedItems.size === 0}
          className="mb-3 w-full rounded-xl bg-white py-3 text-center font-semibold text-black disabled:opacity-50"
        >
          {loading ? "Processing..." : `Pay $${selectedTotal}`}
        </button>
        <button
          onClick={onClose}
          className="w-full py-3 text-center text-sm text-zinc-400"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
