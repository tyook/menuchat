import { create } from "zustand";
import type { ParsedOrderItem, MenuItem, MenuItemVariant, MenuItemModifier, TabOrder, TabResponse } from "@/types";

type OrderStep = "welcome" | "ordering" | "cart" | "payment" | "submitted" | "tab_review";

interface OrderState {
  step: OrderStep;
  rawInput: string;
  parsedItems: ParsedOrderItem[];
  parsedAllergies: string[];
  totalPrice: string;
  language: string;
  orderId: string | null;
  tableIdentifier: string;
  customerName: string;
  customerPhone: string;
  error: string | null;
  clientSecret: string | null;
  paymentMode: "stripe" | "pos_collected";
  paymentModel: "upfront" | "tab";
  tabId: string | null;
  tabOrders: TabOrder[];
  tabTotal: string;
  tabAmountPaid: string;
  tabAmountRemaining: string;
  tabPaymentId: string | null;

  // Actions
  setStep: (step: OrderStep) => void;
  setRawInput: (input: string) => void;
  setParsedResult: (items: ParsedOrderItem[], allergies: string[], total: string, lang: string) => void;
  addItem: (item: ParsedOrderItem) => void;
  addItemFromMenu: (
    item: MenuItem,
    variant: MenuItemVariant,
    modifiers: MenuItemModifier[],
    quantity: number,
  ) => void;
  removeItem: (index: number) => void;
  updateItemQuantity: (index: number, quantity: number) => void;
  setOrderId: (id: string) => void;
  setTableIdentifier: (table: string) => void;
  setCustomerName: (name: string) => void;
  setCustomerPhone: (phone: string) => void;
  setError: (error: string | null) => void;
  setClientSecret: (secret: string | null) => void;
  setPaymentMode: (mode: "stripe" | "pos_collected") => void;
  setPaymentModel: (model: "upfront" | "tab") => void;
  setTabId: (id: string | null) => void;
  setTabData: (tab: TabResponse) => void;
  setTabPaymentId: (id: string | null) => void;
  reset: () => void;
}

const initialState = {
  step: "welcome" as OrderStep,
  rawInput: "",
  parsedItems: [] as ParsedOrderItem[],
  parsedAllergies: [] as string[],
  totalPrice: "0.00",
  language: "en",
  orderId: null,
  tableIdentifier: "",
  customerName: "",
  customerPhone: "",
  error: null,
  clientSecret: null,
  paymentMode: "stripe" as "stripe" | "pos_collected",
  paymentModel: "upfront" as "upfront" | "tab",
  tabId: null as string | null,
  tabOrders: [] as TabOrder[],
  tabTotal: "0.00",
  tabAmountPaid: "0.00",
  tabAmountRemaining: "0.00",
  tabPaymentId: null as string | null,
};

export const useOrderStore = create<OrderState>((set) => ({
  ...initialState,

  setStep: (step) => set({ step }),
  setRawInput: (rawInput) => set({ rawInput }),
  setParsedResult: (newItems, newAllergies, _totalPrice, language) =>
    set((state) => {
      const combined = [...state.parsedItems, ...newItems];
      const total = combined
        .reduce((sum, i) => sum + parseFloat(i.line_total), 0)
        .toFixed(2);
      const allergies = Array.from(new Set([...state.parsedAllergies, ...newAllergies]));
      return { parsedItems: combined, parsedAllergies: allergies, totalPrice: total, language };
    }),
  addItem: (item) =>
    set((state) => {
      const newItems = [...state.parsedItems, item];
      const newTotal = newItems
        .reduce((sum, i) => sum + parseFloat(i.line_total), 0)
        .toFixed(2);
      return { parsedItems: newItems, totalPrice: newTotal };
    }),
  addItemFromMenu: (menuItem, variant, modifiers, quantity) =>
    set((state) => {
      const lineTotal = (
        (parseFloat(variant.price) +
          modifiers.reduce((sum, m) => sum + parseFloat(m.price_adjustment), 0)) *
        quantity
      ).toFixed(2);
      const newItem: ParsedOrderItem = {
        menu_item_id: menuItem.id,
        name: menuItem.name,
        variant: { id: variant.id, label: variant.label, price: variant.price },
        quantity,
        modifiers,
        special_requests: "",
        line_total: lineTotal,
      };
      const newItems = [...state.parsedItems, newItem];
      const newTotal = newItems
        .reduce((sum, i) => sum + parseFloat(i.line_total), 0)
        .toFixed(2);
      return { parsedItems: newItems, totalPrice: newTotal };
    }),
  removeItem: (index) =>
    set((state) => {
      const newItems = state.parsedItems.filter((_, i) => i !== index);
      const newTotal = newItems
        .reduce((sum, item) => sum + parseFloat(item.line_total), 0)
        .toFixed(2);
      return { parsedItems: newItems, totalPrice: newTotal };
    }),
  updateItemQuantity: (index, quantity) =>
    set((state) => {
      const newItems = [...state.parsedItems];
      const item = { ...newItems[index] };
      const unitPrice = parseFloat(item.line_total) / item.quantity;
      item.quantity = quantity;
      item.line_total = (unitPrice * quantity).toFixed(2);
      newItems[index] = item;
      const newTotal = newItems
        .reduce((sum, i) => sum + parseFloat(i.line_total), 0)
        .toFixed(2);
      return { parsedItems: newItems, totalPrice: newTotal };
    }),
  setOrderId: (orderId) => set({ orderId }),
  setTableIdentifier: (tableIdentifier) => set({ tableIdentifier }),
  setCustomerName: (customerName) => set({ customerName }),
  setCustomerPhone: (customerPhone) => set({ customerPhone }),
  setError: (error) => set({ error }),
  setClientSecret: (clientSecret) => set({ clientSecret }),
  setPaymentMode: (paymentMode) => set({ paymentMode }),
  setPaymentModel: (paymentModel) => set({ paymentModel }),
  setTabId: (tabId) => set({ tabId }),
  setTabData: (tab) => set({
    tabId: tab.id,
    tabOrders: tab.orders,
    tabTotal: tab.total,
    tabAmountPaid: tab.amount_paid,
    tabAmountRemaining: tab.amount_remaining,
  }),
  setTabPaymentId: (tabPaymentId) => set({ tabPaymentId }),
  reset: () => set(initialState),
}));
