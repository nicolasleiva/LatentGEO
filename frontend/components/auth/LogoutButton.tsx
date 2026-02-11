"use client";

export default function LogoutButton() {
    return (
        <a
            href="/auth/logout"
            className="inline-flex items-center justify-center px-6 py-3 text-base font-semibold text-white bg-red-500 rounded-lg shadow-sm hover:bg-red-600 transition-all duration-300"
        >
            Log Out
        </a>
    );
}
