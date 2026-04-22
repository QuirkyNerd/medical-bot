/// <reference types="next" />
/// <reference types="next/types/global" />

declare module 'next/server' {
  export class NextRequest extends Request {
    nextUrl: any;
    cookies: any;
  }
  export class NextResponse extends Response {
    static json(body: any, init?: any): NextResponse;
    static next(init?: any): NextResponse;
    static redirect(url: string | URL, init?: any): NextResponse;
    static rewrite(destination: string | URL, init?: any): NextResponse;
  }
}
