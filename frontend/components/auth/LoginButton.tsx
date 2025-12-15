"use client";

export default function LoginButton() {
    return (
        <a
            href="/auth/login"
            className="inline-flex items-center justify-center px-6 py-3 text-base font-semibold text-white bg-blue-600 rounded-lg shadow-lg hover:bg-blue-700 transition-all duration-300 hover:scale-105"
        >
            Log In
        </a>
    );
}
