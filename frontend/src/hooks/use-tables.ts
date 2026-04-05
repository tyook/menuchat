import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchTables, createTable, updateTable, deleteTable } from "@/lib/api";

export function useTables(slug: string) {
  return useQuery({
    queryKey: ["tables", slug],
    queryFn: () => fetchTables(slug),
    enabled: !!slug,
  });
}

export function useCreateTable(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; number: string }) =>
      createTable(slug, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tables", slug] });
    },
  });
}

export function useUpdateTable(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      tableId,
      data,
    }: {
      tableId: string;
      data: Partial<{ name: string; number: string; is_active: boolean }>;
    }) => updateTable(slug, tableId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tables", slug] });
    },
  });
}

export function useDeleteTable(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (tableId: string) => deleteTable(slug, tableId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tables", slug] });
    },
  });
}
