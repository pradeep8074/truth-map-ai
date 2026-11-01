import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { BrowserRouter, MemoryRouter } from "react-router-dom";
import App from "../App";
import { NAVIGATION_ITEMS } from "../lib/navigation";

describe("TruthMap AI - UI Shell & Navigation Architecture", () => {
  it("renders the Intelligence Command Center with honest metrics and branding", () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    );

    // Verify brand
    expect(screen.getAllByText(/TRUTHMAP/i).length).toBeGreaterThan(0);

    // Verify Overview Metric Area - Honest Zero Counts (No Fake Data)
    expect(screen.getByText("Active Investigations")).toBeInTheDocument();
    expect(screen.getByText("Sources Indexed")).toBeInTheDocument();
    expect(screen.getByText("Pending Requirements")).toBeInTheDocument();
    expect(screen.getAllByText("Conflicting Evidence").length).toBeGreaterThan(0);

    // Verify empty state for Recent Investigations
    expect(screen.getByText("Recent Investigations")).toBeInTheDocument();
    expect(screen.getByText("No Investigations Yet")).toBeInTheDocument();

    // Verify Quick Actions area
    expect(screen.getAllByText("Start an Investigation").length).toBeGreaterThan(0);
    expect(screen.getAllByText("View Evidence Map").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Investigation Reports").length).toBeGreaterThan(0);
  });

  it("toggles the sidebar collapse state when the collapse button is clicked", () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    );

    const toggleBtn = screen.getByTitle("Collapse Sidebar");
    expect(toggleBtn).toBeInTheDocument();

    fireEvent.click(toggleBtn);

    // Button should now offer to expand
    expect(screen.getByTitle("Expand Sidebar")).toBeInTheDocument();

    fireEvent.click(screen.getByTitle("Expand Sidebar"));
    expect(screen.getByTitle("Collapse Sidebar")).toBeInTheDocument();
  });

  it("opens and closes the Command Palette via button and Escape key", () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    );

    const searchTrigger = screen.getByTitle(/Search or jump to module/i);
    fireEvent.click(searchTrigger);

    expect(
      screen.getByPlaceholderText(/Type a command or jump to an intelligence module/i)
    ).toBeInTheDocument();

    // Press Escape to close
    fireEvent.keyDown(window, { key: "Escape" });
    expect(
      screen.queryByPlaceholderText(/Type a command or jump to an intelligence module/i)
    ).not.toBeInTheDocument();
  });

  // Verify all navigation modules
  NAVIGATION_ITEMS.forEach((navItem) => {
    it(`navigates correctly to route "${navItem.path}" and renders ${navItem.name}`, () => {
      render(
        <MemoryRouter initialEntries={[navItem.path]}>
          <App />
        </MemoryRouter>
      );

      // Verify the page title or breadcrumb reflects the module
      const occurrences = screen.getAllByText(new RegExp(navItem.name, "i"));
      expect(occurrences.length).toBeGreaterThan(0);

      if (navItem.path === "/investigations") {
        expect(screen.getByRole("heading", { name: /Start an Investigation/i })).toBeInTheDocument();
        expect(screen.getByText(/Investigation Question/i)).toBeInTheDocument();
        expect(screen.getAllByText(/Web Links/i).length).toBeGreaterThan(0);
      } else if (navItem.path === "/decision-contract") {
        expect(screen.getByRole("heading", { name: /Decision Criteria/i })).toBeInTheDocument();
        expect(screen.getByText(/Target Investigation/i)).toBeInTheDocument();
      } else if (navItem.path === "/evidence-explorer") {
        expect(screen.getAllByText(/Evidence Explorer/i).length).toBeGreaterThan(0);
        expect(screen.getByText(/Target Investigation/i)).toBeInTheDocument();
      } else if (navItem.path === "/evidence-graph") {
        expect(screen.getByText(/Investigation:/i)).toBeInTheDocument();
        expect(screen.getByText(/All Nodes/i)).toBeInTheDocument();
      } else if (navItem.path === "/conflict-intelligence") {
        expect(screen.getAllByText(/Conflicting Evidence/i).length).toBeGreaterThan(0);
      } else if (navItem.path === "/evidence-sufficiency") {
        expect(screen.getAllByText(/Evidence Coverage/i).length).toBeGreaterThan(0);
      } else if (navItem.path === "/stress-test") {
        expect(screen.getAllByText(/Test Your Decision/i).length).toBeGreaterThan(0);
      } else if (navItem.path === "/reports") {
        expect(screen.getAllByText(/Decision Intelligence Report Engine/i).length).toBeGreaterThan(0);
      } else if (navItem.path === "/fragility-index") {
        expect(screen.getByRole("heading", { name: /Decision Fragility Index/i })).toBeInTheDocument();
      } else if (navItem.path === "/verification-navigator") {
        expect(screen.getAllByText(/Verification Navigator/i).length).toBeGreaterThan(0);
      } else if (navItem.path === "/temporal-intelligence") {
        expect(screen.getAllByText(/Timeline & Freshness/i).length).toBeGreaterThan(0);
      } else if (navItem.path === "/settings") {
        expect(screen.getAllByText(/System Settings/i).length).toBeGreaterThan(0);
        expect(screen.getByText(/Runtime Environment/i)).toBeInTheDocument();
      }
    });
  });
});
