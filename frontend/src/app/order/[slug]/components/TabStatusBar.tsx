"use client";

import { useOrderStore } from "@/stores/order-store";

export default function TabStatusBar() {
  const { paymentModel, tabTotal, tabOrders, setStep } = useOrderStore();

  if (paymentModel !== "tab" || tabOrders.length === 0) return null;

  return (
    <div className="sticky top-0 z-40 flex items-center justify-between bg-zinc-800 px-4 py-2 text-sm text-zinc-200">
      <span>
        Tab open &middot; {tabOrders.length} order{tabOrders.length !== 1 ? "s" : ""} &middot; ${tabTotal}
      </span>
      <button
        onClick={() => setStep("tab_review")}
        className="rounded-md bg-white/10 px-3 py-1 text-xs font-medium hover:bg-white/20"
      >
        View Tab
      </button>
    </div>
  );
}
