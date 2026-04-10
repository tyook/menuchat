"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { Trash2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useRequireRestaurantAccess } from "@/hooks/use-auth";
import { useRestaurant } from "@/hooks/use-restaurant";
import { useUpdateTaxRate } from "@/hooks/use-update-tax-rate";
import { useTables, useCreateTable, useDeleteTable } from "@/hooks/use-tables";
import { apiFetch } from "@/lib/api";
import type { Table } from "@/types";

export default function SettingsPage() {
  const params = useParams<{ slug: string }>();
  const isAuthenticated = useRequireRestaurantAccess();
  const [taxRate, setTaxRate] = useState<string | null>(null);
  const [taxMessage, setTaxMessage] = useState("");
  const [paymentModel, setPaymentModel] = useState<string | null>(null);
  const [pmMessage, setPmMessage] = useState("");
  const [newTableName, setNewTableName] = useState("");
  const [newTableNumber, setNewTableNumber] = useState("");

  const { data: restaurant } = useRestaurant(params.slug);
  const updateTaxRate = useUpdateTaxRate(params.slug);
  const { data: tables = [], isLoading: tablesLoading, error: tablesError } = useTables(params.slug);
  const createTable = useCreateTable(params.slug);
  const deleteTable = useDeleteTable(params.slug);

  const displayTaxRate = taxRate ?? restaurant?.tax_rate ?? "";
  const displayPaymentModel = paymentModel ?? restaurant?.payment_model ?? "upfront";

  const handleSavePaymentModel = async () => {
    setPmMessage("");
    try {
      await apiFetch(`/api/restaurants/${params.slug}/`, {
        method: "PATCH",
        body: JSON.stringify({ payment_model: displayPaymentModel }),
      });
      setPmMessage("Saved");
    } catch {
      setPmMessage("Failed to save");
    }
  };

  const handleSaveTax = () => {
    setTaxMessage("");
    updateTaxRate.mutate(displayTaxRate, {
      onSuccess: () => setTaxMessage("Saved"),
      onError: () => setTaxMessage("Failed to save"),
    });
  };

  const baseUrl = typeof window !== "undefined" ? window.location.origin : "";

  const getOrderUrl = (tableNumber?: string) => {
    if (tableNumber) {
      return `${baseUrl}/order/${params.slug}/${tableNumber}`;
    }
    return `${baseUrl}/order/${params.slug}`;
  };

  const handleAddTable = () => {
    const name = newTableName.trim();
    const number = newTableNumber.trim();
    if (!name || !number) return;
    createTable.mutate(
      { name, number },
      {
        onSuccess: () => {
          setNewTableName("");
          setNewTableNumber("");
        },
      }
    );
  };

  const handleDeleteTable = (table: Table) => {
    if (!window.confirm(`Delete table "${table.name}" (#${table.number})? Existing QR codes for this table will stop working.`)) {
      return;
    }
    deleteTable.mutate(table.id);
  };

  if (isAuthenticated === null) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (isAuthenticated === false) {
    return null;
  }

  const activeTables = tables.filter((t: Table) => t.is_active);

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto">
        <Link
          href="/account/restaurants"
          className="text-sm text-muted-foreground hover:underline"
        >
          Back to dashboard
        </Link>
        <h1 className="text-2xl font-bold mb-6">Settings & QR Codes</h1>

        {/* Tax Rate */}
        <Card className="bg-card border border-border rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Tax Rate</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Set the sales tax percentage for this restaurant. This will be
            applied to all orders.
          </p>
          <div className="flex items-end gap-2">
            <div className="w-40">
              <Label className="text-muted-foreground text-sm" htmlFor="tax-rate">Rate (%)</Label>
              <Input
                id="tax-rate"
                type="number"
                step="0.001"
                min="0"
                max="99"
                value={displayTaxRate}
                onChange={(e) => setTaxRate(e.target.value)}
                placeholder="0.000"
              />
            </div>
            <Button variant="gradient" onClick={handleSaveTax} disabled={updateTaxRate.isPending}>
              {updateTaxRate.isPending ? "Saving..." : "Save"}
            </Button>
            {taxMessage && (
              <span className="text-sm text-muted-foreground ml-2">
                {taxMessage}
              </span>
            )}
          </div>
        </Card>

        {/* Payment Model */}
        <Card className="bg-card border border-border rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Payment Model</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Choose when customers pay for their orders.
          </p>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Label className="text-muted-foreground text-sm">Model</Label>
              <select
                value={displayPaymentModel}
                onChange={(e) => setPaymentModel(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="upfront">Pay Upfront (pay before order goes to kitchen)</option>
                <option value="tab">Open Tab (order first, pay later)</option>
              </select>
            </div>
            <Button variant="gradient" onClick={handleSavePaymentModel}>
              Save
            </Button>
            {pmMessage && (
              <span className="text-sm text-muted-foreground ml-2">
                {pmMessage}
              </span>
            )}
          </div>
        </Card>

        {/* Counter QR (no table) */}
        <Card className="bg-card border border-border rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">
            Counter / Pickup QR Code
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            For counter service without table numbers.
          </p>
          <div className="flex items-center gap-6">
            <QRCodeSVG value={getOrderUrl()} size={150} />
            <div>
              <p className="text-sm font-mono break-all">{getOrderUrl()}</p>
            </div>
          </div>
        </Card>

        {/* Table Management */}
        <Card className="bg-card border border-border rounded-2xl p-6">
          <h2 className="text-lg font-semibold mb-4">Table Management</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Add tables and generate per-table QR codes for dine-in ordering.
          </p>

          {/* Add new table */}
          <div className="flex gap-2 mb-6">
            <div className="flex-1">
              <Label>Table Name</Label>
              <Input
                value={newTableName}
                onChange={(e) => setNewTableName(e.target.value)}
                placeholder="e.g. Patio 3"
              />
            </div>
            <div className="w-32">
              <Label>Number</Label>
              <Input
                value={newTableNumber}
                onChange={(e) => setNewTableNumber(e.target.value)}
                placeholder="e.g. A1"
              />
            </div>
            <Button
              variant="gradient"
              className="mt-6"
              onClick={handleAddTable}
              disabled={createTable.isPending || !newTableName.trim() || !newTableNumber.trim()}
            >
              <Plus className="h-4 w-4 mr-1" />
              {createTable.isPending ? "Adding..." : "Add"}
            </Button>
          </div>

          {createTable.isError && (
            <p className="text-sm text-destructive mb-4">
              {createTable.error?.message || "Failed to add table. The number may already exist."}
            </p>
          )}

          {/* Table list with QR codes */}
          {tablesLoading && (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
            </div>
          )}

          {tablesError && (
            <p className="text-sm text-destructive text-center py-4">
              Failed to load tables.
            </p>
          )}

          {!tablesLoading && !tablesError && activeTables.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {activeTables.map((table: Table) => (
                <div
                  key={table.id}
                  className="flex flex-col items-center p-4 bg-card border border-border rounded-2xl relative group"
                >
                  <button
                    onClick={() => handleDeleteTable(table)}
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                    title="Delete table"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                  <QRCodeSVG value={getOrderUrl(table.number)} size={120} />
                  <p className="font-semibold mt-2">{table.name}</p>
                  <p className="text-xs text-muted-foreground">#{table.number}</p>
                  <p className="text-xs text-muted-foreground break-all text-center mt-1">
                    {getOrderUrl(table.number)}
                  </p>
                </div>
              ))}
            </div>
          )}

          {!tablesLoading && !tablesError && activeTables.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">
              No tables yet. Add your first table above.
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}
