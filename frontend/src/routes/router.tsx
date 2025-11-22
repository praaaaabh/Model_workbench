import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "../components/AppLayout";
import { Home } from "./Home";
import { ModelDetail } from "./ModelDetail";
import { ModelLibrary } from "./ModelLibrary";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: <Home />,
      },
      {
        path: "models",
        element: <ModelLibrary />,
      },
      {
        path: "models/:id",
        element: <ModelDetail />,
      },
      {
        path: "about",
        element: <div>About this project</div>,
      },
    ],
  },
]);
