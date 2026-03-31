"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  usePOSConnect,
  usePOSConnection,
  usePOSConnectionUpdate,
  usePOSDisconnect,
} from "@/hooks/use-pos-connection";

export default function POSIntegrationsPage() {
  const params = useParams<{ slug: string }>();
  const searchParams = useSearchParams();
  const slug = params.slug;

  const { data: connection, isLoading, error } = usePOSConnection(slug);
  const connect = usePOSConnect();
  const disconnect = usePOSDisconnect(slug);
  const updateConnection = usePOSConnectionUpdate(slug);

  // Local state for location ID input (avoid PATCH on every keystroke)
  const [locationId, setLocationId] = useState("");

  useEffect(() => {
    if (connection?.external_location_id != null) {
      setLocationId(connection.external_location_id);
    }
  }, [connection?.external_location_id]);

  const justConnected = searchParams.get("connected");
  const oauthError = searchParams.get("error");

  if (isLoading) {
    return <div className="p-6">Loading...</div>;
  }

  if (error) {
    return (
      <div className="p-6 text-destructive">
        Failed to load POS connection. Please try again later.
      </div>
    );
  }

  const isConnected = connection?.is_connected ?? false;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold">POS Integration</h1>

      {justConnected && (
        <div className="rounded-md bg-success/10 p-4 text-success">
          Successfully connected to {justConnected}!
        </div>
      )}

      {oauthError && (
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          Failed to connect. Please try again.
        </div>
      )}

      {/* Connection Status */}
      <Card className="bg-card border border-border rounded-2xl p-6">
        <h2 className="text-lg font-semibold">Connection Status</h2>
        <div className="mt-4 flex items-center gap-3">
          <span
            className={`h-3 w-3 rounded-full ${
              isConnected ? "bg-success" : "bg-muted-foreground/30"
            }`}
          />
          <span>
            {isConnected
              ? `Connected to ${connection?.pos_type}`
              : "No POS connected"}
          </span>
          {isConnected && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-success/10 text-success font-medium">Active</span>
          )}
        </div>

        {!isConnected && (
          <div className="mt-4 flex gap-3">
            <Button
              variant="gradient"
              onClick={() => connect.mutate({ slug, posType: "square" })}
              disabled={connect.isPending}
            >
              {connect.isPending ? "Connecting..." : "Connect Square"}
            </Button>
            <Button variant="outline" disabled title="Coming soon">
              Connect Toast (Coming Soon)
            </Button>
          </div>
        )}

        {isConnected && (
          <Button
            variant="outline"
            className="mt-4 border-destructive text-destructive hover:bg-destructive/10"
            onClick={() => {
              if (window.confirm("Disconnect POS? Orders will no longer sync.")) {
                disconnect.mutate();
              }
            }}
            disabled={disconnect.isPending}
          >
            Disconnect
          </Button>
        )}
      </Card>

      {/* Location Selector */}
      {isConnected && (
        <Card className="bg-card border border-border rounded-2xl p-6">
          <h2 className="text-lg font-semibold">POS Location</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Enter the location ID from your POS dashboard for the location that should receive QR orders.
          </p>
          <div className="mt-4 flex gap-3">
            <Input
              type="text"
              value={locationId}
              onChange={(e) => setLocationId(e.target.value)}
              placeholder="e.g., L1234ABC (Square) or GUID (Toast)"
              className="flex-1"
            />
            <Button
              variant="gradient"
              onClick={() =>
                updateConnection.mutate({ external_location_id: locationId })
              }
              disabled={updateConnection.isPending || locationId === (connection?.external_location_id ?? "")}
            >
              {updateConnection.isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </Card>
      )}

      {/* Payment Mode */}
      {isConnected && (
        <Card className="bg-card border border-border rounded-2xl p-6">
          <h2 className="text-lg font-semibold">Payment Mode</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose how payments are collected for QR orders.
          </p>
          <div className="mt-4 space-y-3">
            <label className="flex items-start gap-3">
              <input
                type="radio"
                name="payment_mode"
                value="stripe"
                checked={connection?.payment_mode === "stripe"}
                onChange={() =>
                  updateConnection.mutate({ payment_mode: "stripe" })
                }
                className="mt-1"
              />
              <div>
                <div className="font-medium">Pay online (Stripe)</div>
                <div className="text-sm text-muted-foreground">
                  Customers pay through the app. Orders appear as paid in your POS.
                </div>
              </div>
            </label>
            <label className="flex items-start gap-3">
              <input
                type="radio"
                name="payment_mode"
                value="pos_collected"
                checked={connection?.payment_mode === "pos_collected"}
                onChange={() =>
                  updateConnection.mutate({ payment_mode: "pos_collected" })
                }
                className="mt-1"
              />
              <div>
                <div className="font-medium">Pay at counter (POS)</div>
                <div className="text-sm text-muted-foreground">
                  Orders are sent to your POS. Customers pay at the counter or table.
                </div>
              </div>
            </label>
          </div>
        </Card>
      )}
    </div>
  );
}
