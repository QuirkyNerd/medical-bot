import { NextResponse } from 'next/server';
import { streamWithProvider } from '@/lib/providers';

// We need to use nodejs or edge runtime.
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(req: Request) {
  try {
    const args = await req.json();
    
    const stream = await streamWithProvider(args);

    const readable = new ReadableStream({
      async start(controller) {
        try {
          for await (const chunk of stream) {
            const payload = JSON.stringify({
              choices: [{ delta: { content: chunk } }]
            });
            controller.enqueue(new TextEncoder().encode(`data: ${payload}\n\n`));
          }
          controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n'));
          controller.close();
        } catch (err: any) {
          console.error('Chat error:', err);
          const errorPayload = JSON.stringify({ error: err.message || String(err) });
          controller.enqueue(new TextEncoder().encode(`data: ${errorPayload}\n\n`));
          controller.close();
        }
      }
    });

    return new Response(readable, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
      },
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 400 });
  }
}
