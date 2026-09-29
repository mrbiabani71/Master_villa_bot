import { Router, type IRouter } from "express";
import healthRouter from "./health";
import villasRouter from "./villas";
import requestsRouter from "./requests";

const router: IRouter = Router();

router.use(healthRouter);
router.use(villasRouter);
router.use(requestsRouter);

export default router;
