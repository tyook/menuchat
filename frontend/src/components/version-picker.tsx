"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ChevronDown, Check, Pencil, Trash2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import type { MenuVersion } from "@/types";
import {
  useMenuVersions,
  useActivateVersion,
  useRenameVersion,
  useDeleteVersion,
} from "@/hooks/use-menu-versions";

interface VersionPickerProps {
  slug: string;
}

export function VersionPicker({ slug }: VersionPickerProps) {
  const { data: versions, isLoading } = useMenuVersions(slug);
  const activateMutation = useActivateVersion(slug);
  const renameMutation = useRenameVersion(slug);
  const deleteMutation = useDeleteVersion(slug);
  const { toast } = useToast();

  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");

  if (isLoading || !versions) return null;

  const activeVersion = versions.find((v) => v.is_active);

  const handleActivate = async (versionId: number) => {
    try {
      await activateMutation.mutateAsync(versionId);
      toast({ title: "Version activated", description: "Menu version activated." });
    } catch {
      toast({ title: "Error", description: "Failed to activate version.", variant: "destructive" });
    }
  };

  const handleStartRename = (version: MenuVersion) => {
    setRenamingId(version.id);
    setRenameValue(version.name);
  };

  const handleRename = async () => {
    if (!renamingId || !renameValue.trim()) return;
    try {
      await renameMutation.mutateAsync({ versionId: renamingId, name: renameValue.trim() });
      toast({ title: "Renamed", description: "Version renamed." });
    } catch {
      toast({ title: "Error", description: "Failed to rename version.", variant: "destructive" });
    }
    setRenamingId(null);
  };

  const handleDelete = async (versionId: number) => {
    try {
      await deleteMutation.mutateAsync(versionId);
      toast({ title: "Deleted", description: "Version deleted." });
    } catch {
      toast({ title: "Error", description: "Cannot delete the active version.", variant: "destructive" });
    }
  };

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground">
        Active: <strong>{activeVersion?.name || "None"}</strong>
      </span>

      {versions.length > 1 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              {versions.length} versions <ChevronDown className="h-3 w-3 ml-1" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-72">
            {versions.map((v) => (
              <div key={v.id}>
                {renamingId === v.id ? (
                  <div className="flex items-center gap-1 px-2 py-1.5">
                    <Input
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleRename()}
                      className="h-7 text-sm"
                      autoFocus
                    />
                    <Button size="sm" variant="ghost" onClick={handleRename}>
                      <Check className="h-3 w-3" />
                    </Button>
                  </div>
                ) : (
                  <DropdownMenuItem
                    className="flex items-center justify-between"
                    onSelect={(e) => e.preventDefault()}
                  >
                    <div className="flex items-center gap-2">
                      {v.is_active && <Check className="h-3 w-3 text-green-600" />}
                      <div>
                        <p className="text-sm font-medium">{v.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {v.item_count} items · {v.source === "ai_upload" ? "AI" : "Manual"}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      {!v.is_active && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleActivate(v.id)}
                          className="h-6 text-xs"
                        >
                          Activate
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleStartRename(v)}
                        className="h-6 px-1"
                      >
                        <Pencil className="h-3 w-3" />
                      </Button>
                      {!v.is_active && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 px-1 text-destructive hover:text-destructive"
                          onClick={() => handleDelete(v.id)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  </DropdownMenuItem>
                )}
              </div>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
