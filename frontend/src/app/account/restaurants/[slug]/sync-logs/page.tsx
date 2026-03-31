"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  useMarkResolved,
  usePOSSyncLogs,
  useRetryAllSync,
  useRetrySync,
} from "@/hooks/use-pos-sync-logs";

const STATUS_CLASS: Record<string, string> = {
  pending: "text-muted-foreground",
  success: "text-success",
  failed: "text-destructive",
  retrying: "text-muted-foreground",
  manually_resolved: "text-muted-foreground",
};

export default function POSSyncLogsPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  const { data: logs, isLoading, error } = usePOSSyncLogs(slug, statusFilter);
  const retrySync = useRetrySync(slug);
  const retryAll = useRetryAllSync(slug);
  const markResolved = useMarkResolved(slug);

  const failedCount = logs?.filter((l) => l.status === "failed").length ?? 0;
  const pendingCount =
    logs?.filter((l) => l.status === "pending" || l.status === "retrying")
      .length ?? 0;

  if (error) {
    return (
      <div className="p-6 text-destructive">
        Failed to load sync logs. Please try again later.
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">POS Sync Status</h1>
        {failedCount > 0 && (
          <Button
            variant="gradient"
            onClick={() => retryAll.mutate()}
            disabled={retryAll.isPending}
          >
            {retryAll.isPending
              ? "Retrying..."
              : `Retry All Failed (${failedCount})`}
          </Button>
        )}
      </div>

      <div className="flex gap-4">
        {failedCount > 0 && (
          <Badge variant="destructive">{failedCount} failed</Badge>
        )}
        {pendingCount > 0 && (
          <Badge variant="secondary">{pendingCount} pending</Badge>
        )}
      </div>

      <div className="flex gap-2">
        {["all", "failed", "pending", "retrying", "success", "manually_resolved"].map(
          (s) => (
            <Button
              key={s}
              variant={(s === "all" && !statusFilter) || statusFilter === s ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter(s === "all" ? undefined : s)}
            >
              {s === "all" ? "All" : s.replace("_", " ")}
            </Button>
          )
        )}
      </div>

      {isLoading ? (
        <div>Loading...</div>
      ) : (
        <div className="bg-card border border-border rounded-2xl overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border text-muted-foreground">
            <tr>
              <th className="pb-2 px-4 pt-4">Order</th>
              <th className="pb-2 px-4 pt-4">Date</th>
              <th className="pb-2 px-4 pt-4">Status</th>
              <th className="pb-2 px-4 pt-4">POS Order ID</th>
              <th className="pb-2 px-4 pt-4">Attempts</th>
              <th className="pb-2 px-4 pt-4">Error</th>
              <th className="pb-2 px-4 pt-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {logs?.map((log) => (
              <tr key={log.id} className="border-b border-border hover:bg-muted/50 transition-colors">
                <td className="py-3 px-4 font-mono text-xs">
                  <Link
                    href={`/account/orders/${log.order_id}`}
                    className="text-primary hover:underline"
                  >
                    {log.order_id.slice(0, 8)}...
                  </Link>
                </td>
                <td className="py-3 px-4">
                  {new Date(log.order_created_at).toLocaleString()}
                </td>
                <td className="py-3 px-4">
                  <span className={`text-xs font-medium ${STATUS_CLASS[log.status] ?? "text-muted-foreground"}`}>
                    {log.status.replace("_", " ")}
                  </span>
                </td>
                <td className="py-3 px-4 font-mono text-xs">
                  {log.external_order_id ?? "-"}
                </td>
                <td className="py-3 px-4">{log.attempt_count}</td>
                <td className="max-w-xs truncate py-3 px-4 text-xs text-muted-foreground">
                  {log.last_error ?? "-"}
                </td>
                <td className="py-3 px-4">
                  <div className="flex gap-2">
                    {log.status === "failed" && (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => retrySync.mutate(log.order_id)}
                        >
                          Retry
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => markResolved.mutate(log.id)}
                        >
                          Mark Resolved
                        </Button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}

      {logs?.length === 0 && (
        <div className="py-12 text-center text-muted-foreground">
          No sync logs found.
        </div>
      )}
    </div>
  );
}
