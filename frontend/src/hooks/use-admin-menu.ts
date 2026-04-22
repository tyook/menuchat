import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { MenuItemStatus } from "@/types";

interface Variant {
  id: number;
  label: string;
  price: string;
  is_default: boolean;
}

interface Modifier {
  id: number;
  name: string;
  price_adjustment: string;
}

interface MenuItemFull {
  id: number;
  name: string;
  description: string;
  image_url: string;
  status: MenuItemStatus;
  is_upsellable: boolean;
  is_featured: boolean;
  sort_order: number;
  variants: Variant[];
  modifiers: Modifier[];
}

interface Category {
  id: number;
  name: string;
  sort_order: number;
  is_active: boolean;
  items: MenuItemFull[];
}

export interface AdminMenu {
  restaurant_name: string;
  categories: Category[];
}

export function useAdminMenu(slug: string, enabled = true) {
  return useQuery({
    queryKey: ["admin-menu", slug],
    queryFn: () => apiFetch<AdminMenu>(`/api/restaurants/${slug}/menu/`),
    enabled: !!slug && enabled,
  });
}

export function useAddCategory(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: { name: string; sort_order: number }) =>
      apiFetch(`/api/restaurants/${slug}/categories/`, {
        method: "POST",
        body: JSON.stringify(params),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}

export function useAddMenuItem(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: {
      category_id: number;
      name: string;
      description: string;
      sort_order: number;
      variants: { label: string; price: string; is_default: boolean }[];
      modifiers: { name: string; price_adjustment: string }[];
    }) =>
      apiFetch(`/api/restaurants/${slug}/items/`, {
        method: "POST",
        body: JSON.stringify(params),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}

export function useUpdateMenuItem(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      itemId,
      ...data
    }: {
      itemId: number;
      name?: string;
      description?: string;
      variants?: { id?: number; label: string; price: string; is_default: boolean }[];
      modifiers?: { id?: number; name: string; price_adjustment: string }[];
    }) =>
      apiFetch(`/api/restaurants/${slug}/items/${itemId}/`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}

export function useToggleUpsellable(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ itemId, is_upsellable }: { itemId: number; is_upsellable: boolean }) =>
      apiFetch(`/api/restaurants/${slug}/items/${itemId}/`, {
        method: "PATCH",
        body: JSON.stringify({ is_upsellable }),
      }),
    onMutate: async ({ itemId, is_upsellable }) => {
      await queryClient.cancelQueries({ queryKey: ["admin-menu", slug] });
      const previous = queryClient.getQueryData<AdminMenu>(["admin-menu", slug]);
      if (previous) {
        queryClient.setQueryData<AdminMenu>(["admin-menu", slug], {
          ...previous,
          categories: previous.categories.map((cat) => ({
            ...cat,
            items: cat.items.map((item) =>
              item.id === itemId ? { ...item, is_upsellable } : item
            ),
          })),
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["admin-menu", slug], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}

export function useToggleFeatured(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ itemId, is_featured }: { itemId: number; is_featured: boolean }) =>
      apiFetch(`/api/restaurants/${slug}/items/${itemId}/`, {
        method: "PATCH",
        body: JSON.stringify({ is_featured }),
      }),
    onMutate: async ({ itemId, is_featured }) => {
      await queryClient.cancelQueries({ queryKey: ["admin-menu", slug] });
      const previous = queryClient.getQueryData<AdminMenu>(["admin-menu", slug]);
      if (previous) {
        queryClient.setQueryData<AdminMenu>(["admin-menu", slug], {
          ...previous,
          categories: previous.categories.map((cat) => ({
            ...cat,
            items: cat.items.map((item) =>
              item.id === itemId ? { ...item, is_featured } : item
            ),
          })),
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["admin-menu", slug], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}

export function useUpdateMenuItemImage(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ itemId, image_url }: { itemId: number; image_url: string }) =>
      apiFetch(`/api/restaurants/${slug}/items/${itemId}/`, {
        method: "PATCH",
        body: JSON.stringify({ image_url }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}

export function useSetMenuItemStatus(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ itemId, status }: { itemId: number; status: MenuItemStatus }) =>
      apiFetch(`/api/restaurants/${slug}/items/${itemId}/`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    onMutate: async ({ itemId, status }) => {
      await queryClient.cancelQueries({ queryKey: ["admin-menu", slug] });
      const previous = queryClient.getQueryData<AdminMenu>(["admin-menu", slug]);
      if (previous) {
        queryClient.setQueryData<AdminMenu>(["admin-menu", slug], {
          ...previous,
          categories: previous.categories.map((cat) => ({
            ...cat,
            items: cat.items.map((item) =>
              item.id === itemId ? { ...item, status } : item
            ),
          })),
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["admin-menu", slug], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}

export function useDeleteMenuItem(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (itemId: number) =>
      apiFetch(`/api/restaurants/${slug}/items/${itemId}/`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}
