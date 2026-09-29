import { rateLimit, type RateLimitRequestHandler } from "express-rate-limit";

const WINDOW_MS = 60 * 1000;
const MAX_REQUESTS_PER_WINDOW = 60;

export const apiRateLimiter: RateLimitRequestHandler = rateLimit({
  windowMs: WINDOW_MS,
  limit: MAX_REQUESTS_PER_WINDOW,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many requests, please try again later." },
  handler: (req, res) => {
    res.status(429).json({
      error: "Too many requests, please try again later.",
      retry_after_seconds: Math.ceil(WINDOW_MS / 1000),
    });
  },
});
