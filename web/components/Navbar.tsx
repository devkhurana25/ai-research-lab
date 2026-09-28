"use client";

import { useRouter } from "next/navigation";
import { logoutUser } from "@/lib/api";

export default function Navbar() {
  const router = useRouter();

  const handleLogout = () => {
    logoutUser();
    router.push("/login");
  };

  return (
    <nav>
      <button onClick={handleLogout}>
        Logout
      </button>
    </nav>
  );
}