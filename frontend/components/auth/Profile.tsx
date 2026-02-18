"use client";

import { useUser } from "@auth0/nextjs-auth0/client";
import Image from "next/image";

export default function Profile() {
  const { user, isLoading, error } = useUser();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-gray-600">Loading profile...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
        <p className="text-red-600">Error loading profile: {error.message}</p>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="flex items-center gap-4 p-4 bg-white rounded-lg shadow-md border border-gray-200">
      <div className="relative w-12 h-12">
        <Image
          src={user.picture || "/default-avatar.png"}
          alt={user.name || "User profile"}
          fill
          className="rounded-full object-cover border-2 border-blue-500"
          unoptimized
        />
      </div>
      <div>
        <h3 className="font-semibold text-gray-900">{user.name}</h3>
        <p className="text-sm text-gray-500">{user.email}</p>
      </div>
    </div>
  );
}
