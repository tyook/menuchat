"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Trash2, ChevronDown, ChevronRight, ImagePlus, Loader2, X } from "lucide-react";
import { useUploadMenuItemImage } from "@/hooks/use-menu-upload";
import { useToast } from "@/hooks/use-toast";
import type { ParsedMenu, ParsedMenuCategory, ParsedMenuItem, ParsedMenuVariant } from "@/types";

interface ParsedMenuEditorProps {
  slug: string;
  menu: ParsedMenu;
  onChange: (menu: ParsedMenu) => void;
}

const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"];

export function ParsedMenuEditor({ slug, menu, onChange }: ParsedMenuEditorProps) {
  const [collapsedCategories, setCollapsedCategories] = useState<Set<number>>(new Set());
  const [uploadingKey, setUploadingKey] = useState<string | null>(null);
  const uploadMutation = useUploadMenuItemImage(slug);
  const { toast } = useToast();

  const toggleCategory = (index: number) => {
    const next = new Set(collapsedCategories);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    setCollapsedCategories(next);
  };

  const updateCategory = (catIndex: number, updates: Partial<ParsedMenuCategory>) => {
    const categories = [...menu.categories];
    categories[catIndex] = { ...categories[catIndex], ...updates };
    onChange({ categories });
  };

  const removeCategory = (catIndex: number) => {
    onChange({ categories: menu.categories.filter((_, i) => i !== catIndex) });
  };

  const updateItem = (catIndex: number, itemIndex: number, updates: Partial<ParsedMenuItem>) => {
    const categories = [...menu.categories];
    const items = [...categories[catIndex].items];
    items[itemIndex] = { ...items[itemIndex], ...updates };
    categories[catIndex] = { ...categories[catIndex], items };
    onChange({ categories });
  };

  const removeItem = (catIndex: number, itemIndex: number) => {
    const categories = [...menu.categories];
    categories[catIndex] = {
      ...categories[catIndex],
      items: categories[catIndex].items.filter((_, i) => i !== itemIndex),
    };
    onChange({ categories });
  };

  const updateVariant = (
    catIndex: number,
    itemIndex: number,
    varIndex: number,
    updates: Partial<ParsedMenuVariant>
  ) => {
    const categories = [...menu.categories];
    const items = [...categories[catIndex].items];
    const variants = [...items[itemIndex].variants];
    variants[varIndex] = { ...variants[varIndex], ...updates };
    items[itemIndex] = { ...items[itemIndex], variants };
    categories[catIndex] = { ...categories[catIndex], items };
    onChange({ categories });
  };

  const handleImageUpload = async (
    catIndex: number,
    itemIndex: number,
    file: File
  ) => {
    const key = `${catIndex}-${itemIndex}`;
    setUploadingKey(key);
    try {
      const result = await uploadMutation.mutateAsync(file);
      updateItem(catIndex, itemIndex, { image_url: result.image_url });
    } catch {
      toast({
        title: "Upload failed",
        description: "Failed to upload image. Please try again.",
        variant: "destructive",
      });
    } finally {
      setUploadingKey(null);
    }
  };

  const totalItems = menu.categories.reduce((sum, cat) => sum + cat.items.length, 0);

  return (
    <div>
      <p className="text-sm text-muted-foreground mb-4">
        AI found <strong>{menu.categories.length}</strong> categories and{" "}
        <strong>{totalItems}</strong> items. Edit anything that looks off.
      </p>

      <div className="space-y-3">
        {menu.categories.map((cat, catIndex) => (
          <div key={catIndex} className="bg-card border border-border rounded-2xl overflow-hidden">
            <div className="flex items-center justify-between bg-muted/50 px-4 py-2">
              <button
                className="flex items-center gap-2 text-foreground font-semibold text-sm"
                onClick={() => toggleCategory(catIndex)}
              >
                {collapsedCategories.has(catIndex) ? (
                  <ChevronRight className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
                <Input
                  value={cat.name}
                  onChange={(e) => updateCategory(catIndex, { name: e.target.value })}
                  className="h-7 w-48 font-semibold"
                  onClick={(e) => e.stopPropagation()}
                />
                <span className="text-muted-foreground font-normal">
                  ({cat.items.length} items)
                </span>
              </button>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={() => removeCategory(catIndex)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>

            {!collapsedCategories.has(catIndex) && (
              <div className="divide-y divide-border">
                {cat.items.map((item, itemIndex) => {
                  const itemKey = `${catIndex}-${itemIndex}`;
                  const isUploading = uploadingKey === itemKey;
                  return (
                    <div key={itemIndex} className="border-b border-border p-3 hover:bg-muted/50 last:border-b-0">
                      <div className="flex items-start gap-2">
                        <ItemImageUpload
                          imageUrl={item.image_url}
                          isUploading={isUploading}
                          onUpload={(file) => handleImageUpload(catIndex, itemIndex, file)}
                          onRemove={() => updateItem(catIndex, itemIndex, { image_url: null })}
                        />
                        <div className="flex-1 space-y-1">
                          <Input
                            value={item.name}
                            onChange={(e) =>
                              updateItem(catIndex, itemIndex, { name: e.target.value })
                            }
                            className="h-7 font-medium"
                          />
                          <Input
                            value={item.description || ""}
                            onChange={(e) =>
                              updateItem(catIndex, itemIndex, {
                                description: e.target.value || null,
                              })
                            }
                            placeholder="Description (optional)"
                            className="h-7 text-sm text-muted-foreground"
                          />
                          <div className="flex items-center gap-2 mt-1">
                            <input
                              type="checkbox"
                              id={`featured-${catIndex}-${itemIndex}`}
                              checked={item.is_featured ?? false}
                              onChange={(e) =>
                                updateItem(catIndex, itemIndex, { is_featured: e.target.checked })
                              }
                              className="h-3.5 w-3.5 rounded border-muted-foreground/30"
                            />
                            <label
                              htmlFor={`featured-${catIndex}-${itemIndex}`}
                              className="text-xs text-muted-foreground cursor-pointer"
                            >
                              Featured
                            </label>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {item.variants.map((variant, varIndex) => (
                            <div key={varIndex} className="flex items-center gap-1">
                              {item.variants.length > 1 && (
                                <Input
                                  value={variant.label}
                                  onChange={(e) =>
                                    updateVariant(catIndex, itemIndex, varIndex, {
                                      label: e.target.value,
                                    })
                                  }
                                  className="h-7 w-20 text-xs"
                                />
                              )}
                              <div className="flex items-center">
                                <span className="text-sm">$</span>
                                <Input
                                  value={variant.price}
                                  onChange={(e) =>
                                    updateVariant(catIndex, itemIndex, varIndex, {
                                      price: e.target.value,
                                    })
                                  }
                                  className="h-7 w-20 text-right"
                                />
                              </div>
                            </div>
                          ))}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => removeItem(catIndex, itemIndex)}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ItemImageUpload({
  imageUrl,
  isUploading,
  onUpload,
  onRemove,
}: {
  imageUrl: string | null;
  isUploading: boolean;
  onUpload: (file: File) => void;
  onRemove: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) return;
    onUpload(file);
    e.target.value = "";
  };

  if (isUploading) {
    return (
      <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center shrink-0">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (imageUrl) {
    return (
      <div className="relative w-12 h-12 shrink-0 group">
        <img
          src={imageUrl}
          alt=""
          className="w-12 h-12 rounded-lg object-cover"
        />
        <button
          onClick={onRemove}
          className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <X className="h-3 w-3" />
        </button>
      </div>
    );
  }

  return (
    <>
      <button
        onClick={() => inputRef.current?.click()}
        className="w-12 h-12 rounded-lg border-2 border-dashed border-border hover:border-primary/40 flex items-center justify-center shrink-0 transition-colors"
        title="Upload item photo"
      >
        <ImagePlus className="h-4 w-4 text-muted-foreground" />
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_IMAGE_TYPES.join(",")}
        onChange={handleChange}
        className="hidden"
      />
    </>
  );
}
