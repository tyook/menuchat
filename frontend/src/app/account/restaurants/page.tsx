"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthStore } from "@/stores/auth-store";
import { useRequireRestaurantAccess } from "@/hooks/use-auth";
import { useMyRestaurants } from "@/hooks/use-my-restaurants";
import { useCreateRestaurant } from "@/hooks/use-create-restaurant";

export default function RestaurantsDashboard() {
  const isAuthenticated = useRequireRestaurantAccess();
  const { logout } = useAuthStore();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newStreetAddress, setNewStreetAddress] = useState("");
  const [newCity, setNewCity] = useState("");
  const [newState, setNewState] = useState("");
  const [newZipCode, setNewZipCode] = useState("");
  const [newHomepage, setNewHomepage] = useState("");
  const [newLogoUrl, setNewLogoUrl] = useState("");

  const { data: restaurants, isLoading } = useMyRestaurants(isAuthenticated === true);
  const createRestaurant = useCreateRestaurant();

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    createRestaurant.mutate(
      {
        name: newName,
        slug: newSlug,
        phone: newPhone || undefined,
        street_address: newStreetAddress || undefined,
        city: newCity || undefined,
        state: newState || undefined,
        zip_code: newZipCode || undefined,
        homepage: newHomepage || undefined,
        logo_url: newLogoUrl || undefined,
      },
      {
        onSuccess: () => {
          setShowCreate(false);
          setNewName("");
          setNewSlug("");
          setNewPhone("");
          setNewStreetAddress("");
          setNewCity("");
          setNewState("");
          setNewZipCode("");
          setNewHomepage("");
          setNewLogoUrl("");
        },
      }
    );
  };

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

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-2xl font-bold">My Restaurants</h1>
          <div className="flex gap-2">
            <Button variant="gradient" onClick={() => setShowCreate(!showCreate)}>
              + New Restaurant
            </Button>
            <Button variant="outline" onClick={logout}>
              Sign Out
            </Button>
          </div>
        </div>

        {showCreate && (
          <Card className="bg-card border border-border rounded-2xl p-6 mb-6">
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <Label>Restaurant Name</Label>
                <Input
                  value={newName}
                  onChange={(e) => {
                    setNewName(e.target.value);
                    setNewSlug(
                      e.target.value
                        .toLowerCase()
                        .replace(/[^a-z0-9]+/g, "-")
                        .replace(/^-|-$/g, "")
                    );
                  }}
                  placeholder="My Pizza Place"
                  required
                />
              </div>
              <div>
                <Label>URL Slug</Label>
                <Input
                  value={newSlug}
                  onChange={(e) => setNewSlug(e.target.value)}
                  placeholder="my-pizza-place"
                  required
                />
              </div>
              <div>
                <Label>Phone Number <span className="text-muted-foreground text-xs">(optional)</span></Label>
                <Input
                  value={newPhone}
                  onChange={(e) => setNewPhone(e.target.value)}
                  placeholder="(555) 123-4567"
                />
              </div>
              <div>
                <Label>Street Address <span className="text-muted-foreground text-xs">(optional)</span></Label>
                <Input
                  value={newStreetAddress}
                  onChange={(e) => setNewStreetAddress(e.target.value)}
                  placeholder="123 Main St"
                />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label>City <span className="text-muted-foreground text-xs">(optional)</span></Label>
                  <Input
                    value={newCity}
                    onChange={(e) => setNewCity(e.target.value)}
                    placeholder="San Francisco"
                  />
                </div>
                <div>
                  <Label>State <span className="text-muted-foreground text-xs">(optional)</span></Label>
                  <Input
                    value={newState}
                    onChange={(e) => setNewState(e.target.value)}
                    placeholder="CA"
                  />
                </div>
                <div>
                  <Label>ZIP Code <span className="text-muted-foreground text-xs">(optional)</span></Label>
                  <Input
                    value={newZipCode}
                    onChange={(e) => setNewZipCode(e.target.value)}
                    placeholder="94102"
                  />
                </div>
              </div>
              <div>
                <Label>Homepage URL <span className="text-muted-foreground text-xs">(optional)</span></Label>
                <Input
                  value={newHomepage}
                  onChange={(e) => setNewHomepage(e.target.value)}
                  placeholder="https://www.mypizzaplace.com"
                  type="url"
                />
              </div>
              <div>
                <Label>Logo URL <span className="text-muted-foreground text-xs">(optional)</span></Label>
                <Input
                  value={newLogoUrl}
                  onChange={(e) => setNewLogoUrl(e.target.value)}
                  placeholder="https://example.com/logo.png"
                  type="url"
                />
              </div>
              <Button variant="gradient" type="submit" disabled={createRestaurant.isPending}>
                {createRestaurant.isPending ? "Creating..." : "Create"}
              </Button>
            </form>
          </Card>
        )}

        <div className="grid gap-4">
          {restaurants?.map((r) => (
            <Card key={r.id} className="bg-card border border-border rounded-2xl p-5 hover:border-primary/30 transition-colors">
              <div className="flex justify-between items-center">
                <div>
                  <h2 className="text-xl font-semibold text-foreground">{r.name}</h2>
                  <p className="text-sm text-muted-foreground">/{r.slug}</p>
                  {r.subscription && (
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-muted">
                        {r.subscription.plan_name}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        r.subscription.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                      }`}>
                        {r.subscription.status.replace("_", " ")}
                      </span>
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <Link href={`/account/restaurants/${r.slug}/menu`}>
                    <Button variant="outline" size="sm">Menu</Button>
                  </Link>
                  <Link href={`/account/restaurants/${r.slug}/orders`}>
                    <Button variant="outline" size="sm">Orders</Button>
                  </Link>
                  <Link href={`/account/restaurants/${r.slug}/billing`}>
                    <Button variant="outline" size="sm">Billing</Button>
                  </Link>
                  <Link href={`/account/restaurants/${r.slug}/settings`}>
                    <Button variant="outline" size="sm">Settings</Button>
                  </Link>
                  <Link href={`/kitchen/${r.slug}`}>
                    <Button size="sm">Kitchen</Button>
                  </Link>
                </div>
              </div>
            </Card>
          ))}
          {(!restaurants || restaurants.length === 0) && (
            <p className="text-center text-muted-foreground py-12">
              No restaurants yet. Create one to get started.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
