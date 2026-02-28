"use client";

import { logoutAllSessions } from "@/lib/app-auth";

export default function LogoutButton() {
  return (
    <button
      type="button"
      onClick={() => {
        void logoutAllSessions();
      }}
      className="inline-flex items-center justify-center px-6 py-3 text-base font-semibold text-white bg-red-500 rounded-lg shadow-sm hover:bg-red-600 transition-all duration-300"
    >
      Log Out
    </button>
  );
}
