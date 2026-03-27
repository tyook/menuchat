"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCreateRestaurant } from "@/hooks/use-create-restaurant";
import { GooglePlacesAutocomplete } from "@/components/google-places-autocomplete";
import { useToast } from "@/hooks/use-toast";

interface RestaurantDetailsStepProps {
  onCreated: (slug: string) => void;
  onBack: () => void;
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

interface AddressFields {
  street_address: string;
  city: string;
  state: string;
  zip_code: string;
  country: string;
  google_place_id: string;
  latitude: number | null;
  longitude: number | null;
}

export function RestaurantDetailsStep({ onCreated, onBack }: RestaurantDetailsStepProps) {
  const createRestaurant = useCreateRestaurant();
  const { toast } = useToast();

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState<AddressFields | null>(null);

  const handleNameChange = (value: string) => {
    setName(value);
    setSlug(slugify(value));
  };

  const handleAddressSelect = useCallback((addr: AddressFields) => {
    setAddress(addr);
  }, []);

  const handleSubmit = () => {
    if (!name.trim() || !slug.trim()) return;

    createRestaurant.mutate(
      {
        name: name.trim(),
        slug: slug.trim(),
        phone: phone || undefined,
        street_address: address?.street_address || undefined,
        city: address?.city || undefined,
        state: address?.state || undefined,
        zip_code: address?.zip_code || undefined,
        country: address?.country || undefined,
        google_place_id: address?.google_place_id || undefined,
        latitude: address?.latitude,
        longitude: address?.longitude,
      },
      {
        onSuccess: (data) => {
          onCreated(data.slug);
        },
        onError: (err) => {
          toast({
            title: "Failed to create restaurant",
            description: err instanceof Error ? err.message : "Unknown error",
            variant: "destructive",
          });
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Restaurant Details</h1>
        <p className="text-muted-foreground mt-1">
          Tell us about your restaurant to get started.
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <Label htmlFor="restaurant-name">Restaurant Name</Label>
          <Input
            id="restaurant-name"
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="e.g. Joe's Diner"
          />
        </div>

        <div>
          <Label htmlFor="restaurant-slug">URL Slug</Label>
          <Input
            id="restaurant-slug"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="joes-diner"
          />
          <p className="text-xs text-muted-foreground mt-1">
            Your menu will be available at /r/{slug || "your-slug"}
          </p>
        </div>

        <div>
          <Label htmlFor="restaurant-phone">Phone (optional)</Label>
          <Input
            id="restaurant-phone"
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="(555) 123-4567"
          />
        </div>

        <div>
          <Label>Address (optional)</Label>
          <GooglePlacesAutocomplete onSelect={handleAddressSelect} />
        </div>

        {address && (
          <div className="rounded-md border p-3 text-sm text-muted-foreground space-y-1">
            {address.street_address && <p>{address.street_address}</p>}
            <p>
              {[address.city, address.state, address.zip_code].filter(Boolean).join(", ")}
            </p>
            {address.country && <p>{address.country}</p>}
          </div>
        )}
      </div>

      <div className="flex gap-3 pt-2">
        <Button
          onClick={handleSubmit}
          className="flex-1"
          disabled={!name.trim() || !slug.trim() || createRestaurant.isPending}
        >
          {createRestaurant.isPending ? "Creating..." : "Create Restaurant"}
        </Button>
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
      </div>
    </div>
  );
}
