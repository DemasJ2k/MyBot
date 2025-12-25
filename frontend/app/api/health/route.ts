/**
 * Frontend Health Check Endpoint
 * Prompt 18 - Production Deployment
 *
 * Provides health status for load balancers and orchestration
 */

import { NextResponse } from 'next/server'

export async function GET() {
  return NextResponse.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    service: 'flowrex-frontend',
    version: process.env.VERSION || '1.0.0',
    environment: process.env.NODE_ENV || 'development',
  })
}
