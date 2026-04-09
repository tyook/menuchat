"use client";

import { useState } from "react";
import { useOrderStore } from "@/stores/order-store";
import { createTabPayment } from "@/lib/api";

interface SplitEvenModalProps {
  slug: string;
  onClose: () => void;
}

export default function SplitEvenModal({ slug, onClose }: SplitEvenModalProps) {
  const { tabId, tabTotal, tabAmountRemaining } = useOrderStore();
  const [splitCount, setSplitCount] = useState(2);
  const [loading, setLoading] = useState(false);

  const remaining = parseFloat(tabAmountRemaining || tabTotal);
  const perPerson = (remaining / splitCount).toFixed(2);

  const handlePay = async () => {
    if (!tabId) return;
    setLoading(true);
    try {
      const { client_secret, payment_id } = await createTabPayment(
        slug,
        tabId,
        "split_even",
        splitCount
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
      <div className="w-full max-w-md rounded-t-2xl bg-zinc-900 p-6">
        <h3 className="mb-4 text-lg font-bold text-white">Split Evenly</h3>

        <div className="mb-4 flex items-center justify-between">
          <span className="text-zinc-300">Number of people</span>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSplitCount(Math.max(2, splitCount - 1))}
              className="h-8 w-8 rounded-full bg-zinc-700 text-white"
            >
              -
            </button>
            <span className="min-w-[2rem] text-center text-lg font-bold text-white">
              {splitCount}
            </span>
            <button
              onClick={() => setSplitCount(splitCount + 1)}
              className="h-8 w-8 rounded-full bg-zinc-700 text-white"
            >
              +
            </button>
          </div>
        </div>

        <div className="mb-6 rounded-lg bg-zinc-800 p-4 text-center">
          <div className="text-sm text-zinc-400">Your share</div>
          <div className="text-2xl font-bold text-white">${perPerson}</div>
        </div>

        <button
          onClick={handlePay}
          disabled={loading}
          className="mb-3 w-full rounded-xl bg-white py-3 text-center font-semibold text-black"
        >
          {loading ? "Processing..." : `Pay $${perPerson}`}
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
