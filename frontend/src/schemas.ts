import { z } from 'zod'
const meta = z.object({ sessionId: z.string(), predictionId: z.string(), timestamp: z.string(), source: z.string(), status: z.enum(['idle', 'waiting', 'processing', 'ready', 'stale', 'unavailable', 'error', 'offline', 'reconnecting']), modelVersion: z.string().optional() })
export const binaryPredictionSchema = meta.extend({ winProbability: z.number().min(0).max(1), lossProbability: z.number().min(0).max(1) })
export const mainPredictionSchema = meta.extend({ predictedClass: z.enum(['eliminated', 'elimination', 'victory']), eliminatedProbability: z.number().min(0).max(1), eliminationProbability: z.number().min(0).max(1), victoryProbability: z.number().min(0).max(1), confidence: z.number().min(0).max(1), latencyMs: z.number().nonnegative() })
export function validateBinary(value: unknown) { return binaryPredictionSchema.parse(value) }
export function validateMain(value: unknown) { return mainPredictionSchema.parse(value) }
