import { NextResponse } from 'next/server';
import { verifyConnection } from '@/lib/providers';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(req: Request) {
  try {
    const args = await req.json();
    const result = await verifyConnection(args);
    return NextResponse.json(result);
  } catch (err: any) {
    return NextResponse.json(
      { success: false, error: err.message },
      { status: 400 }
    );
  }
}
