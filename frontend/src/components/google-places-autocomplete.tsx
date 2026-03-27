"use client";

import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";

interface AddressComponents {
  street_address: string;
  city: string;
  state: string;
  zip_code: string;
  country: string;
  google_place_id: string;
  latitude: number | null;
  longitude: number | null;
}

interface GooglePlacesAutocompleteProps {
  onSelect: (address: AddressComponents) => void;
  defaultValue?: string;
}

function parsePlace(place: google.maps.places.PlaceResult): AddressComponents {
  const components: AddressComponents = {
    street_address: "",
    city: "",
    state: "",
    zip_code: "",
    country: "",
    google_place_id: place.place_id || "",
    latitude: place.geometry?.location?.lat() ?? null,
    longitude: place.geometry?.location?.lng() ?? null,
  };

  let streetNumber = "";
  let route = "";

  for (const component of place.address_components || []) {
    const types = component.types;
    if (types.includes("street_number")) {
      streetNumber = component.long_name;
    } else if (types.includes("route")) {
      route = component.long_name;
    } else if (types.includes("locality")) {
      components.city = component.long_name;
    } else if (types.includes("administrative_area_level_1")) {
      components.state = component.short_name;
    } else if (types.includes("postal_code")) {
      components.zip_code = component.long_name;
    } else if (types.includes("country")) {
      components.country = component.short_name;
    }
  }

  components.street_address = [streetNumber, route].filter(Boolean).join(" ");

  return components;
}

export function GooglePlacesAutocomplete({ onSelect, defaultValue }: GooglePlacesAutocompleteProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const autocompleteRef = useRef<google.maps.places.Autocomplete | null>(null);
  const [value, setValue] = useState(defaultValue || "");

  useEffect(() => {
    if (typeof google === "undefined" || !google.maps?.places || !inputRef.current) {
      return;
    }

    const autocomplete = new google.maps.places.Autocomplete(inputRef.current, {
      types: ["address"],
      fields: ["address_components", "geometry", "place_id"],
    });

    autocomplete.addListener("place_changed", () => {
      const place = autocomplete.getPlace();
      if (place.address_components) {
        const parsed = parsePlace(place);
        setValue(place.formatted_address || parsed.street_address);
        onSelect(parsed);
      }
    });

    autocompleteRef.current = autocomplete;

    return () => {
      google.maps.event.clearInstanceListeners(autocomplete);
    };
  }, [onSelect]);

  return (
    <Input
      ref={inputRef}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      placeholder="Start typing an address..."
    />
  );
}
