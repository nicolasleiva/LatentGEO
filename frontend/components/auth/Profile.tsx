"use client";

import { useUser } from "@auth0/nextjs-auth0/client";

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
            <img
                src={user.picture || "/default-avatar.png"}
                alt={user.name || "User profile"}
                className="w-12 h-12 rounded-full object-cover border-2 border-blue-500"
                onError={(e) => {
                    const target = e.target as HTMLImageElement;
                    target.src = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='48' height='48' viewBox='0 0 48 48'%3E%3Ccircle cx='24' cy='24' r='24' fill='%233b82f6'/%3E%3Cpath d='M24 22c3.6 0 6.5-2.9 6.5-6.5S27.6 9 24 9s-6.5 2.9-6.5 6.5S20.4 22 24 22zm0 3.3c-4.4 0-13 2.2-13 6.5v1.6c0 .9.7 1.6 1.6 1.6h22.8c.9 0 1.6-.7 1.6-1.6v-1.6c0-4.3-8.6-6.5-13-6.5z' fill='%23fff'/%3E%3C/svg%3E`;
                }}
            />
            <div>
                <h3 className="font-semibold text-gray-900">{user.name}</h3>
                <p className="text-sm text-gray-500">{user.email}</p>
            </div>
        </div>
    );
}
