"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useRequireAuth } from "@/hooks/use-auth";
import { useProfile, useUpdateProfile } from "@/hooks/use-profile";
import { usePreferencesStore } from "@/stores/preferences-store";
import { useToast } from "@/hooks/use-toast";
import { SPEECH_LANGUAGES } from "@/lib/constants";
import { Store, X } from "lucide-react";
import Link from "next/link";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

const PREDEFINED_DIETARY_PREFERENCES = [
  "Vegetarian",
  "Vegan",
  "Halal",
  "Kosher",
  "Gluten-Free",
  "Dairy-Free",
  "Nut-Free",
];

const PREDEFINED_ALLERGIES = [
  "Peanuts",
  "Tree Nuts",
  "Shellfish",
  "Dairy",
  "Eggs",
  "Soy",
  "Wheat",
  "Fish",
];

export default function CustomerProfilePage() {
  const isAuthenticated = useRequireAuth();
  const { toast } = useToast();
  const { data: profile, isLoading, error } = useProfile();
  const updateProfileMutation = useUpdateProfile();
  const { setPreferredLanguage, setAllergyNote } = usePreferencesStore();

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [dietaryPreferences, setDietaryPreferences] = useState<string[]>([]);
  const [allergies, setAllergies] = useState<string[]>([]);
  const [preferredLanguage, setPreferredLanguageLocal] = useState("en-US");
  const [customDietaryInput, setCustomDietaryInput] = useState("");
  const [customAllergyInput, setCustomAllergyInput] = useState("");

  useEffect(() => {
    if (profile) {
      setFirstName(profile.first_name || "");
      setLastName(profile.last_name || "");
      setPhone(profile.phone || "");
      setDietaryPreferences(profile.dietary_preferences || []);
      setAllergies(profile.allergies || []);
      setPreferredLanguageLocal(profile.preferred_language || "en-US");
    }
  }, [profile]);

  if (isAuthenticated === null || isLoading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto" />
      </div>
    );
  }

  if (isAuthenticated === false) {
    return null;
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 text-center">
        <p className="text-destructive">Failed to load profile.</p>
        <p className="text-sm text-muted-foreground mt-2">
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </div>
    );
  }

  const toggleDietaryPreference = (pref: string) => {
    setDietaryPreferences((prev) =>
      prev.includes(pref) ? prev.filter((p) => p !== pref) : [...prev, pref]
    );
  };

  const addCustomDietaryPreference = () => {
    const trimmed = customDietaryInput.trim();
    if (trimmed && !dietaryPreferences.includes(trimmed)) {
      setDietaryPreferences([...dietaryPreferences, trimmed]);
      setCustomDietaryInput("");
    }
  };

  const removeDietaryPreference = (pref: string) => {
    setDietaryPreferences(dietaryPreferences.filter((p) => p !== pref));
  };

  const toggleAllergy = (allergy: string) => {
    setAllergies((prev) =>
      prev.includes(allergy) ? prev.filter((a) => a !== allergy) : [...prev, allergy]
    );
  };

  const addCustomAllergy = () => {
    const trimmed = customAllergyInput.trim();
    if (trimmed && !allergies.includes(trimmed)) {
      setAllergies([...allergies, trimmed]);
      setCustomAllergyInput("");
    }
  };

  const removeAllergy = (allergy: string) => {
    setAllergies(allergies.filter((a) => a !== allergy));
  };

  const handleSave = async () => {
    try {
      await updateProfileMutation.mutateAsync({
        first_name: firstName,
        last_name: lastName,
        phone,
        dietary_preferences: dietaryPreferences,
        allergies,
        preferred_language: preferredLanguage,
      });

      // Sync to preferences store
      setPreferredLanguage(preferredLanguage);
      setAllergyNote(allergies.join(", "));

      toast({
        title: "Profile updated",
        description: "Your preferences have been saved successfully.",
      });
    } catch (err) {
      toast({
        title: "Update failed",
        description: err instanceof Error ? err.message : "Failed to update profile",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Profile Settings</h1>

      <div className="space-y-6">
        {/* Restaurant Owner CTA */}
        {profile && !profile.owns_restaurant && (
          <Card className="p-6 bg-gradient-to-r from-green-50 to-emerald-50 border-green-300">
            <div className="flex items-center gap-4">
              <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-green-500 text-white flex items-center justify-center">
                <Store className="h-5 w-5" />
              </div>
              <div className="flex-1">
                <h2 className="text-sm font-semibold">Own a restaurant?</h2>
                <p className="text-xs text-muted-foreground">
                  Register your restaurant and start accepting QR orders
                </p>
              </div>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button size="sm" className="bg-green-600 hover:bg-green-700">
                    Get Started
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Register Your Restaurant</AlertDialogTitle>
                    <AlertDialogDescription asChild>
                      <div>
                        <p className="mb-4">Here&apos;s what you&apos;ll set up:</p>
                        <div className="space-y-3 mb-4">
                          <div className="flex items-start gap-3">
                            <div className="flex-shrink-0 w-7 h-7 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-semibold">
                              1
                            </div>
                            <div>
                              <p className="text-sm font-medium text-foreground">Restaurant details</p>
                              <p className="text-xs text-muted-foreground">Name, address, contact info</p>
                            </div>
                          </div>
                          <div className="flex items-start gap-3">
                            <div className="flex-shrink-0 w-7 h-7 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-semibold">
                              2
                            </div>
                            <div>
                              <p className="text-sm font-medium text-foreground">
                                Menu upload <span className="text-xs font-normal text-muted-foreground">(optional)</span>
                              </p>
                              <p className="text-xs text-muted-foreground">Upload a photo or PDF of your menu</p>
                            </div>
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          You can edit everything later from your dashboard.
                        </p>
                      </div>
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction asChild>
                      <Link href="/account/register-restaurant">Continue</Link>
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </Card>
        )}

        {/* Basic Information */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Basic Information</h2>
          <div className="space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={profile?.email || ""}
                disabled
                className="bg-muted"
              />
              <p className="text-xs text-muted-foreground mt-1">Email cannot be changed</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="first-name">First Name</Label>
                <Input
                  id="first-name"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="First name"
                />
              </div>
              <div>
                <Label htmlFor="last-name">Last Name</Label>
                <Input
                  id="last-name"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Last name"
                />
              </div>
            </div>
            <div>
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="Phone number"
              />
            </div>
          </div>
        </Card>

        {/* Dietary Preferences */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Dietary Preferences</h2>
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {PREDEFINED_DIETARY_PREFERENCES.map((pref) => (
                <Badge
                  key={pref}
                  variant={dietaryPreferences.includes(pref) ? "default" : "outline"}
                  className="cursor-pointer"
                  onClick={() => toggleDietaryPreference(pref)}
                >
                  {pref}
                </Badge>
              ))}
            </div>
            {dietaryPreferences.filter(
              (p) => !PREDEFINED_DIETARY_PREFERENCES.includes(p)
            ).length > 0 && (
              <div className="flex flex-wrap gap-2 pt-2 border-t">
                {dietaryPreferences
                  .filter((p) => !PREDEFINED_DIETARY_PREFERENCES.includes(p))
                  .map((pref) => (
                    <Badge key={pref} variant="secondary" className="gap-1">
                      {pref}
                      <X
                        className="h-3 w-3 cursor-pointer"
                        onClick={() => removeDietaryPreference(pref)}
                      />
                    </Badge>
                  ))}
              </div>
            )}
            <div className="flex gap-2">
              <Input
                value={customDietaryInput}
                onChange={(e) => setCustomDietaryInput(e.target.value)}
                placeholder="Add custom preference..."
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addCustomDietaryPreference();
                  }
                }}
              />
              <Button
                type="button"
                variant="outline"
                onClick={addCustomDietaryPreference}
                disabled={!customDietaryInput.trim()}
              >
                Add
              </Button>
            </div>
          </div>
        </Card>

        {/* Allergies */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Allergies</h2>
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {PREDEFINED_ALLERGIES.map((allergy) => (
                <Badge
                  key={allergy}
                  variant={allergies.includes(allergy) ? "default" : "outline"}
                  className="cursor-pointer"
                  onClick={() => toggleAllergy(allergy)}
                >
                  {allergy}
                </Badge>
              ))}
            </div>
            {allergies.filter((a) => !PREDEFINED_ALLERGIES.includes(a)).length > 0 && (
              <div className="flex flex-wrap gap-2 pt-2 border-t">
                {allergies
                  .filter((a) => !PREDEFINED_ALLERGIES.includes(a))
                  .map((allergy) => (
                    <Badge key={allergy} variant="secondary" className="gap-1">
                      {allergy}
                      <X
                        className="h-3 w-3 cursor-pointer"
                        onClick={() => removeAllergy(allergy)}
                      />
                    </Badge>
                  ))}
              </div>
            )}
            <div className="flex gap-2">
              <Input
                value={customAllergyInput}
                onChange={(e) => setCustomAllergyInput(e.target.value)}
                placeholder="Add custom allergy..."
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addCustomAllergy();
                  }
                }}
              />
              <Button
                type="button"
                variant="outline"
                onClick={addCustomAllergy}
                disabled={!customAllergyInput.trim()}
              >
                Add
              </Button>
            </div>
          </div>
        </Card>

        {/* Preferred Language */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Preferred Language</h2>
          <div>
            <Label htmlFor="language">Language for voice ordering</Label>
            <select
              id="language"
              value={preferredLanguage}
              onChange={(e) => setPreferredLanguageLocal(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {SPEECH_LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.label}
                </option>
              ))}
            </select>
          </div>
        </Card>

        {/* Save Button */}
        <Button
          onClick={handleSave}
          className="w-full"
          disabled={updateProfileMutation.isPending}
        >
          {updateProfileMutation.isPending ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </div>
  );
}
