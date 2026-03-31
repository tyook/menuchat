import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { Restaurant } from "@/types";

interface CreateRestaurantParams {
  name: string;
  slug: string;
  phone?: string;
  street_address?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  country?: string;
  google_place_id?: string;
  latitude?: number | null;
  longitude?: number | null;
  homepage?: string;
  logo_url?: string;
}

export function useCreateRestaurant() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: CreateRestaurantParams) => {
      const body: Record<string, string | number | null> = {
        name: params.name,
        slug: params.slug,
      };
      if (params.phone) body.phone = params.phone;
      if (params.street_address) body.street_address = params.street_address;
      if (params.city) body.city = params.city;
      if (params.state) body.state = params.state;
      if (params.zip_code) body.zip_code = params.zip_code;
      if (params.country) body.country = params.country;
      if (params.google_place_id) body.google_place_id = params.google_place_id;
      if (params.latitude !== undefined) body.latitude = params.latitude;
      if (params.longitude !== undefined) body.longitude = params.longitude;
      if (params.homepage) body.homepage = params.homepage;
      if (params.logo_url) body.logo_url = params.logo_url;

      return apiFetch<Restaurant>("/api/restaurants/", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-restaurants"] });
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}
