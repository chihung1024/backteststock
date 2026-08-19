import app from "./walk_forward_router.js";
import { updateUniverses } from "./universe_updater.js";

export default {
  fetch(request, env, context) {
    return app.fetch(request, env, context);
  },

  async scheduled(controller, env) {
    await updateUniverses(env, {
      cron: controller.cron,
      scheduledTime: controller.scheduledTime,
    });
  },
};
