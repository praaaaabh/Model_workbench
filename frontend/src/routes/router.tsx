import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "../components/AppLayout";

const Home = () => <div>Welcome to Model Workbench</div>;

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
        path: "about",
        element: <div>About this project</div>,
      },
    ],
  },
]);
