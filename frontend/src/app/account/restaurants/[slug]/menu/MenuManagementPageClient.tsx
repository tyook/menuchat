"use client";

import { useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useRequireRestaurantAccess } from "@/hooks/use-auth";
import {
  useAdminMenu,
  useAddCategory,
  useAddMenuItem,
  useDeleteMenuItem,
  useSetMenuItemStatus,
  useToggleFeatured,
  useToggleUpsellable,
  useUpdateMenuItem,
  useUpdateMenuItemImage,
} from "@/hooks/use-admin-menu";
import { useUploadMenuItemImage } from "@/hooks/use-menu-upload";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { MenuUploadModal } from "@/components/menu-upload-modal";
import { VersionPicker } from "@/components/version-picker";

export default function MenuManagementPage() {
  const params = useParams<{ slug: string }>();
  const isAuthenticated = useRequireRestaurantAccess();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [showAddItem, setShowAddItem] = useState<number | null>(null);
  const [newItem, setNewItem] = useState({
    name: "",
    description: "",
    variants: [{ label: "Regular", price: "", is_default: true }] as {
      label: string;
      price: string;
      is_default: boolean;
    }[],
    modifiers: [] as { name: string; price_adjustment: string }[],
  });

  const [editingItemId, setEditingItemId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<{
    name: string;
    description: string;
    variants: { id: number; label: string; price: string; is_default: boolean }[];
    modifiers: { id: number; name: string; price_adjustment: string }[];
  }>({ name: "", description: "", variants: [], modifiers: [] });

  const { data: menu, isLoading } = useAdminMenu(params.slug, isAuthenticated === true);
  const addCategory = useAddCategory(params.slug);
  const addMenuItem = useAddMenuItem(params.slug);
  const deleteMenuItem = useDeleteMenuItem(params.slug);
  const setMenuItemStatus = useSetMenuItemStatus(params.slug);
  const toggleUpsellable = useToggleUpsellable(params.slug);
  const toggleFeatured = useToggleFeatured(params.slug);
  const updateMenuItem = useUpdateMenuItem(params.slug);
  const uploadImage = useUploadMenuItemImage(params.slug);
  const updateItemImage = useUpdateMenuItemImage(params.slug);
  const [uploadingItemId, setUploadingItemId] = useState<number | null>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const pendingItemIdRef = useRef<number | null>(null);

  const handleImageUpload = async (itemId: number, file: File) => {
    setUploadingItemId(itemId);
    try {
      const result = await uploadImage.mutateAsync(file);
      await updateItemImage.mutateAsync({ itemId, image_url: result.image_url });
    } catch {
      // error is handled by mutation
    } finally {
      setUploadingItemId(null);
    }
  };

  const startEditing = (item: {
    id: number;
    name: string;
    description: string;
    variants: { id: number; label: string; price: string; is_default: boolean }[];
    modifiers: { id: number; name: string; price_adjustment: string }[];
  }) => {
    setEditingItemId(item.id);
    setEditForm({
      name: item.name,
      description: item.description || "",
      variants: item.variants.map((v) => ({ ...v })),
      modifiers: item.modifiers.map((m) => ({ ...m })),
    });
  };

  const handleSaveEdit = () => {
    if (!editingItemId) return;
    // Strip temporary negative ids so the backend creates them as new
    const variants = editForm.variants.map((v) =>
      v.id < 0 ? { label: v.label, price: v.price, is_default: v.is_default } : v
    );
    const modifiers = editForm.modifiers.map((m) =>
      m.id < 0 ? { name: m.name, price_adjustment: m.price_adjustment } : m
    );
    updateMenuItem.mutate(
      {
        itemId: editingItemId,
        name: editForm.name,
        description: editForm.description,
        variants,
        modifiers,
      },
      { onSuccess: () => setEditingItemId(null) },
    );
  };

  let nextTempId = -1;
  const addEditVariant = () => {
    const tempId = nextTempId--;
    setEditForm((prev) => ({
      ...prev,
      variants: [...prev.variants, { id: tempId, label: "", price: "", is_default: false }],
    }));
  };

  const removeEditVariant = (index: number) => {
    setEditForm((prev) => {
      const variants = prev.variants.filter((_, i) => i !== index);
      // Ensure at least one default
      if (variants.length > 0 && !variants.some((v) => v.is_default)) {
        variants[0] = { ...variants[0], is_default: true };
      }
      return { ...prev, variants };
    });
  };

  const setDefaultVariant = (index: number) => {
    setEditForm((prev) => ({
      ...prev,
      variants: prev.variants.map((v, i) => ({ ...v, is_default: i === index })),
    }));
  };

  const addEditModifier = () => {
    const tempId = nextTempId--;
    setEditForm((prev) => ({
      ...prev,
      modifiers: [...prev.modifiers, { id: tempId, name: "", price_adjustment: "" }],
    }));
  };

  const removeEditModifier = (index: number) => {
    setEditForm((prev) => ({
      ...prev,
      modifiers: prev.modifiers.filter((_, i) => i !== index),
    }));
  };

  const handleAddCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    addCategory.mutate(
      {
        name: newCategoryName,
        sort_order: (menu?.categories.length || 0) + 1,
      },
      {
        onSuccess: () => setNewCategoryName(""),
      }
    );
  };

  const handleAddItem = (categoryId: number) => {
    addMenuItem.mutate(
      {
        category_id: categoryId,
        name: newItem.name,
        description: newItem.description,
        sort_order: 0,
        variants: newItem.variants,
        modifiers: newItem.modifiers,
      },
      {
        onSuccess: () => {
          setShowAddItem(null);
          setNewItem({
            name: "",
            description: "",
            variants: [{ label: "Regular", price: "", is_default: true }],
            modifiers: [],
          });
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
        <div className="flex items-center justify-between mb-6">
          <div>
            <Link
              href="/account/restaurants"
              className="text-sm text-muted-foreground hover:underline"
            >
              Back to dashboard
            </Link>
            <h1 className="text-2xl font-bold">
              {menu?.restaurant_name} - Menu
            </h1>
            <VersionPicker slug={params.slug} />
          </div>
          <Button
            variant="gradient"
            onClick={() => setUploadOpen(true)}
          >
            Upload Menu Photos
          </Button>
        </div>

        {/* Add Category */}
        <Card className="bg-card border border-border rounded-2xl p-4 mb-6">
          <form onSubmit={handleAddCategory} className="flex gap-2">
            <Input
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              placeholder="New category name (e.g. Appetizers)"
              required
            />
            <Button type="submit" disabled={addCategory.isPending}>
              {addCategory.isPending ? "Adding..." : "Add Category"}
            </Button>
          </form>
        </Card>

        {/* Categories and Items */}
        {menu?.categories.map((cat) => (
          <div key={cat.id} className="mb-8">
            <h2 className="text-xl font-semibold mb-3">{cat.name}</h2>

            <div className="space-y-2 mb-4">
              {cat.items.map((item) => (
                <Card
                  key={item.id}
                  className={`bg-card border border-border rounded-2xl p-4 hover:bg-muted/50 transition-colors ${item.status !== "active" ? "opacity-60" : ""}`}
                >
                  {editingItemId === item.id ? (
                    /* ── Edit mode ── */
                    <div className="space-y-3">
                      <div className="flex gap-3">
                        {item.image_url && (
                          <img
                            src={item.image_url}
                            alt={item.name}
                            className="w-14 h-14 rounded-lg object-cover shrink-0"
                          />
                        )}
                        <div className="flex-1 space-y-2">
                          <div>
                            <Label className="text-xs">Name</Label>
                            <Input
                              value={editForm.name}
                              onChange={(e) =>
                                setEditForm({ ...editForm, name: e.target.value })
                              }
                            />
                          </div>
                          <div>
                            <Label className="text-xs">Description</Label>
                            <Input
                              value={editForm.description}
                              onChange={(e) =>
                                setEditForm({ ...editForm, description: e.target.value })
                              }
                              placeholder="Optional description"
                            />
                          </div>
                        </div>
                      </div>
                      <div>
                        <Label className="text-xs">Variants</Label>
                        <div className="space-y-2 mt-1">
                          {editForm.variants.map((v, vi) => (
                            <div key={v.id} className="flex gap-2 items-center">
                              <div className="grid grid-cols-2 gap-2 flex-1">
                                <Input
                                  value={v.label}
                                  onChange={(e) => {
                                    const variants = [...editForm.variants];
                                    variants[vi] = { ...v, label: e.target.value };
                                    setEditForm({ ...editForm, variants });
                                  }}
                                  placeholder="Label (e.g. Large)"
                                />
                                <Input
                                  type="number"
                                  step="0.01"
                                  value={v.price}
                                  onChange={(e) => {
                                    const variants = [...editForm.variants];
                                    variants[vi] = { ...v, price: e.target.value };
                                    setEditForm({ ...editForm, variants });
                                  }}
                                  placeholder="Price"
                                />
                              </div>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button
                                    type="button"
                                    onClick={() => setDefaultVariant(vi)}
                                    className={`shrink-0 text-xs px-2 py-1 rounded ${v.is_default ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"}`}
                                  >
                                    Default
                                  </button>
                                </TooltipTrigger>
                                <TooltipContent>
                                  <p>Set as the default variant shown to customers</p>
                                </TooltipContent>
                              </Tooltip>
                              {editForm.variants.length > 1 && (
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  className="shrink-0 text-destructive hover:text-destructive h-8 w-8 p-0"
                                  onClick={() => removeEditVariant(vi)}
                                >
                                  ×
                                </Button>
                              )}
                            </div>
                          ))}
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="mt-2"
                          onClick={addEditVariant}
                        >
                          + Add Variant
                        </Button>
                      </div>
                      <div>
                        <Label className="text-xs">Add-ons</Label>
                        <div className="space-y-2 mt-1">
                          {editForm.modifiers.map((m, mi) => (
                            <div key={m.id} className="flex gap-2 items-center">
                              <div className="grid grid-cols-2 gap-2 flex-1">
                                <Input
                                  value={m.name}
                                  onChange={(e) => {
                                    const modifiers = [...editForm.modifiers];
                                    modifiers[mi] = { ...m, name: e.target.value };
                                    setEditForm({ ...editForm, modifiers });
                                  }}
                                  placeholder="Name (e.g. Extra Patty)"
                                />
                                <Input
                                  type="number"
                                  step="0.01"
                                  value={m.price_adjustment}
                                  onChange={(e) => {
                                    const modifiers = [...editForm.modifiers];
                                    modifiers[mi] = { ...m, price_adjustment: e.target.value };
                                    setEditForm({ ...editForm, modifiers });
                                  }}
                                  placeholder="Extra price (e.g. 2.00)"
                                />
                              </div>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="shrink-0 text-destructive hover:text-destructive h-8 w-8 p-0"
                                onClick={() => removeEditModifier(mi)}
                              >
                                ×
                              </Button>
                            </div>
                          ))}
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="mt-2"
                          onClick={addEditModifier}
                        >
                          + Add Add-on
                        </Button>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={handleSaveEdit}
                          disabled={updateMenuItem.isPending}
                        >
                          {updateMenuItem.isPending ? "Saving..." : "Save"}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setEditingItemId(null)}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    /* ── View mode ── */
                    <div className="flex justify-between items-start">
                      <div className="flex gap-3">
                        {item.status === "active" && (
                          <div className="shrink-0">
                            {uploadingItemId === item.id ? (
                              <div className="w-14 h-14 rounded-lg bg-muted flex items-center justify-center">
                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary" />
                              </div>
                            ) : item.image_url ? (
                              <button
                                className="relative w-14 h-14 group"
                                onClick={() => {
                                  pendingItemIdRef.current = item.id;
                                  imageInputRef.current?.click();
                                }}
                                title="Change image"
                              >
                                <img
                                  src={item.image_url}
                                  alt={item.name}
                                  className="w-14 h-14 rounded-lg object-cover"
                                />
                                <div className="absolute inset-0 bg-black/40 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                  <span className="text-white text-[10px] font-medium">Change</span>
                                </div>
                              </button>
                            ) : (
                              <button
                                className="w-14 h-14 rounded-lg border-2 border-dashed border-border hover:border-primary/40 flex items-center justify-center transition-colors"
                                onClick={() => {
                                  pendingItemIdRef.current = item.id;
                                  imageInputRef.current?.click();
                                }}
                                title="Add photo"
                              >
                                <span className="text-muted-foreground text-[10px]">+ Photo</span>
                              </button>
                            )}
                          </div>
                        )}
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{item.name}</span>
                            {item.status === "sold_out" && (
                              <Badge variant="outline" className="border-amber-500/50 text-amber-500">Sold out</Badge>
                            )}
                            {item.status === "inactive" && (
                              <Badge variant="secondary">Inactive</Badge>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {item.description}
                          </p>
                          <div className="text-sm mt-1">
                            {item.variants.map((v) => (
                              <span key={v.id} className="mr-3">
                                {v.label}: ${v.price}
                                {v.is_default && " (default)"}
                              </span>
                            ))}
                          </div>
                          {item.modifiers.length > 0 && (
                            <div className="text-sm text-muted-foreground mt-1">
                              Add-ons:{" "}
                              {item.modifiers
                                .map(
                                  (m) =>
                                    `${m.name} (+$${m.price_adjustment})`
                                )
                                .join(", ")}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {item.status === "active" && (
                          <>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <div className="flex items-center gap-1.5">
                                  <Checkbox
                                    id={`upsell-${item.id}`}
                                    checked={item.is_upsellable}
                                    onCheckedChange={(checked) =>
                                      toggleUpsellable.mutate({
                                        itemId: item.id,
                                        is_upsellable: checked === true,
                                      })
                                    }
                                  />
                                  <Label
                                    htmlFor={`upsell-${item.id}`}
                                    className="text-xs text-muted-foreground cursor-pointer"
                                  >
                                    Upsellable
                                  </Label>
                                </div>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>Checked items may be suggested to customers as add-ons before they submit their order.</p>
                              </TooltipContent>
                            </Tooltip>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <div className="flex items-center gap-1.5">
                                  <Checkbox
                                    id={`featured-${item.id}`}
                                    checked={item.is_featured}
                                    onCheckedChange={(checked) =>
                                      toggleFeatured.mutate({
                                        itemId: item.id,
                                        is_featured: checked === true,
                                      })
                                    }
                                  />
                                  <Label
                                    htmlFor={`featured-${item.id}`}
                                    className="text-xs text-muted-foreground cursor-pointer"
                                  >
                                    Featured
                                  </Label>
                                </div>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>Featured items are prioritized in AI recommendations.</p>
                              </TooltipContent>
                            </Tooltip>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => startEditing(item)}
                            >
                              Edit
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-amber-500 hover:text-amber-400"
                              onClick={() =>
                                setMenuItemStatus.mutate({ itemId: item.id, status: "sold_out" })
                              }
                            >
                              Sold out
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                setMenuItemStatus.mutate({ itemId: item.id, status: "inactive" })
                              }
                            >
                              Deactivate
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive hover:text-destructive"
                              onClick={() => {
                                if (confirm("Permanently delete this item?")) {
                                  deleteMenuItem.mutate(item.id);
                                }
                              }}
                            >
                              Delete
                            </Button>
                          </>
                        )}
                        {(item.status === "sold_out" || item.status === "inactive") && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-green-500 hover:text-green-400"
                              onClick={() =>
                                setMenuItemStatus.mutate({ itemId: item.id, status: "active" })
                              }
                            >
                              Re-activate
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive hover:text-destructive"
                              onClick={() => {
                                if (confirm("Permanently delete this item?")) {
                                  deleteMenuItem.mutate(item.id);
                                }
                              }}
                            >
                              Delete
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </Card>
              ))}
            </div>

            {/* Add Item Form */}
            {showAddItem === cat.id ? (
              <Card className="bg-card border border-border rounded-2xl p-4">
                <div className="space-y-3">
                  <div>
                    <Label>Item Name</Label>
                    <Input
                      value={newItem.name}
                      onChange={(e) =>
                        setNewItem({ ...newItem, name: e.target.value })
                      }
                      placeholder="e.g. Margherita Pizza"
                    />
                  </div>
                  <div>
                    <Label>Description</Label>
                    <Input
                      value={newItem.description}
                      onChange={(e) =>
                        setNewItem({ ...newItem, description: e.target.value })
                      }
                      placeholder="Classic pizza with tomato and mozzarella"
                    />
                  </div>
                  <div>
                    <Label>Variants</Label>
                    <div className="space-y-2 mt-1">
                      {newItem.variants.map((v, vi) => (
                        <div key={vi} className="flex gap-2 items-center">
                          <div className="grid grid-cols-2 gap-2 flex-1">
                            <Input
                              value={v.label}
                              onChange={(e) => {
                                const variants = [...newItem.variants];
                                variants[vi] = { ...v, label: e.target.value };
                                setNewItem({ ...newItem, variants });
                              }}
                              placeholder="Label (e.g. Large)"
                            />
                            <Input
                              type="number"
                              step="0.01"
                              value={v.price}
                              onChange={(e) => {
                                const variants = [...newItem.variants];
                                variants[vi] = { ...v, price: e.target.value };
                                setNewItem({ ...newItem, variants });
                              }}
                              placeholder="Price"
                            />
                          </div>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button
                                type="button"
                                onClick={() => {
                                  const variants = newItem.variants.map((vr, i) => ({
                                    ...vr,
                                    is_default: i === vi,
                                  }));
                                  setNewItem({ ...newItem, variants });
                                }}
                                className={`shrink-0 text-xs px-2 py-1 rounded ${v.is_default ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"}`}
                              >
                                Default
                              </button>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>Set as the default variant shown to customers</p>
                            </TooltipContent>
                          </Tooltip>
                          {newItem.variants.length > 1 && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="shrink-0 text-destructive hover:text-destructive h-8 w-8 p-0"
                              onClick={() => {
                                const variants = newItem.variants.filter((_, i) => i !== vi);
                                if (!variants.some((vr) => vr.is_default)) {
                                  variants[0] = { ...variants[0], is_default: true };
                                }
                                setNewItem({ ...newItem, variants });
                              }}
                            >
                              ×
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="mt-2"
                      onClick={() =>
                        setNewItem({
                          ...newItem,
                          variants: [
                            ...newItem.variants,
                            { label: "", price: "", is_default: false },
                          ],
                        })
                      }
                    >
                      + Add Variant
                    </Button>
                  </div>
                  <div>
                    <Label>Add-ons</Label>
                    <div className="space-y-2 mt-1">
                      {newItem.modifiers.map((m, mi) => (
                        <div key={mi} className="flex gap-2 items-center">
                          <div className="grid grid-cols-2 gap-2 flex-1">
                            <Input
                              value={m.name}
                              onChange={(e) => {
                                const modifiers = [...newItem.modifiers];
                                modifiers[mi] = { ...m, name: e.target.value };
                                setNewItem({ ...newItem, modifiers });
                              }}
                              placeholder="Name (e.g. Extra Patty)"
                            />
                            <Input
                              type="number"
                              step="0.01"
                              value={m.price_adjustment}
                              onChange={(e) => {
                                const modifiers = [...newItem.modifiers];
                                modifiers[mi] = { ...m, price_adjustment: e.target.value };
                                setNewItem({ ...newItem, modifiers });
                              }}
                              placeholder="Extra price (e.g. 2.00)"
                            />
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="shrink-0 text-destructive hover:text-destructive h-8 w-8 p-0"
                            onClick={() => {
                              const modifiers = newItem.modifiers.filter((_, i) => i !== mi);
                              setNewItem({ ...newItem, modifiers });
                            }}
                          >
                            ×
                          </Button>
                        </div>
                      ))}
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="mt-2"
                      onClick={() =>
                        setNewItem({
                          ...newItem,
                          modifiers: [...newItem.modifiers, { name: "", price_adjustment: "" }],
                        })
                      }
                    >
                      + Add Add-on
                    </Button>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={() => handleAddItem(cat.id)}
                      disabled={addMenuItem.isPending}
                    >
                      {addMenuItem.isPending ? "Saving..." : "Save Item"}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setShowAddItem(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              </Card>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAddItem(cat.id)}
              >
                + Add Item to {cat.name}
              </Button>
            )}

            <Separator className="mt-6" />
          </div>
        ))}
      </div>

      <MenuUploadModal
        slug={params.slug}
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        hasExistingMenu={!!menu?.categories?.length}
      />

      {/* Hidden file input for item image uploads */}
      <input
        ref={imageInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          const itemId = pendingItemIdRef.current;
          if (file && itemId) {
            handleImageUpload(itemId, file);
          }
          e.target.value = "";
          pendingItemIdRef.current = null;
        }}
      />
    </div>
  );
}
