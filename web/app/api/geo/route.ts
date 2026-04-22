import { NextResponse } from "next/server";

// Detects private/internal IP addresses (used by the geo-detection hook).
export function isPrivateIp(ip: string): boolean {
  if (!ip) return true;
  if (ip === "::1" || ip === "127.0.0.1") return true;
  if (ip.startsWith("169.254.")) return true;
  if (ip.startsWith("fe80:")) return true;
  if (ip.startsWith("10.")) return true;
  if (ip.startsWith("192.168.")) return true;
  if (/^172\.(1[6-9]|2\d|3[01])\./.test(ip)) return true;
  return false;
}

export async function GET(req: Request) {
  const forwarded = req.headers.get("x-forwarded-for");
  const ip = forwarded ? forwarded.split(",")[0].trim() : "127.0.0.1";

  if (isPrivateIp(ip)) {
    return NextResponse.json({ country: "US", private: true });
  }

  // Minimal stub — in production you'd call a geo-IP provider here
  return NextResponse.json({ country: "US", ip });
}
