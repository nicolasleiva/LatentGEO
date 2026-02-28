"use client";

import Image from "next/image";
import { useAppAuthState, useCombinedProfile } from "@/lib/app-auth";

export default function Profile() {
  const auth = useAppAuthState();
  const profile = useCombinedProfile(auth);

  if (auth.loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-gray-600">Loading profile...</span>
      </div>
    );
  }

  if (!auth.ready) {
    return null;
  }

  return (
    <div className="flex items-center gap-4 p-4 bg-white rounded-lg shadow-md border border-gray-200">
      <div className="relative w-12 h-12">
        <Image
          src={profile.picture || "/default-avatar.png"}
          alt={profile.name || "User profile"}
          fill
          className="rounded-full object-cover border-2 border-blue-500"
          unoptimized
        />
      </div>
      <div>
        <h3 className="font-semibold text-gray-900">{profile.name}</h3>
        <p className="text-sm text-gray-500">{profile.email}</p>
      </div>
    </div>
  );
}
