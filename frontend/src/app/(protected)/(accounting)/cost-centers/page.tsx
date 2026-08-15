"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  CostCenterResponse,
  DepartmentResponse,
  ProjectResponse,
  createCostCenter,
  createDepartment,
  createProject,
  getCostCenters,
  getDepartments,
  getProjects,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

const emptyDeptForm = { dept_code: "", dept_name: "" };
const emptyCenterForm = { center_code: "", center_name: "", department_id: "" };
const emptyProjectForm = {
  project_code: "",
  project_name: "",
  start_date: "",
  end_date: "",
  budget_amount: "",
};

/**
 * Cost Center management: departments, cost centers, and projects.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T242
 */
export default function CostCentersPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [departments, setDepartments] = useState<DepartmentResponse[]>([]);
  const [costCenters, setCostCenters] = useState<CostCenterResponse[]>([]);
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [deptForm, setDeptForm] = useState(emptyDeptForm);
  const [centerForm, setCenterForm] = useState(emptyCenterForm);
  const [projectForm, setProjectForm] = useState(emptyProjectForm);

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [deptRes, centerRes, projectRes] = await Promise.all([
        getDepartments(companyId),
        getCostCenters(companyId),
        getProjects(companyId),
      ]);
      setDepartments(deptRes.data);
      setCostCenters(centerRes.data);
      setProjects(projectRes.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cost accounting data");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateDepartment() {
    if (!deptForm.dept_code || !deptForm.dept_name) {
      setError("Department code and name are required.");
      return;
    }
    setError(null);
    try {
      await createDepartment(companyId, deptForm);
      setDeptForm(emptyDeptForm);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create department");
    }
  }

  async function handleCreateCostCenter() {
    if (!centerForm.center_code || !centerForm.center_name) {
      setError("Cost center code and name are required.");
      return;
    }
    setError(null);
    try {
      await createCostCenter(companyId, {
        center_code: centerForm.center_code,
        center_name: centerForm.center_name,
        department_id: centerForm.department_id || null,
      });
      setCenterForm(emptyCenterForm);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create cost center");
    }
  }

  async function handleCreateProject() {
    if (!projectForm.project_code || !projectForm.project_name) {
      setError("Project code and name are required.");
      return;
    }
    setError(null);
    try {
      await createProject(companyId, {
        project_code: projectForm.project_code,
        project_name: projectForm.project_name,
        start_date: projectForm.start_date || null,
        end_date: projectForm.end_date || null,
        budget_amount: projectForm.budget_amount || null,
      });
      setProjectForm(emptyProjectForm);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    }
  }

  function departmentName(id: string | null): string {
    if (!id) return "—";
    return departments.find((d) => d.id === id)?.dept_name ?? id;
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Cost Centers</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage departments, cost centers, and projects for internal reporting.
          </p>
        </div>
        <Link
          href={`/${companyId}/reports/cost-center-pl`}
          className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Cost Center P&amp;L
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : (
        <>
          <section className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Departments</h2>
            <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <input
                type="text"
                value={deptForm.dept_code}
                onChange={(e) => setDeptForm({ ...deptForm, dept_code: e.target.value })}
                placeholder="Department code"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="text"
                value={deptForm.dept_name}
                onChange={(e) => setDeptForm({ ...deptForm, dept_name: e.target.value })}
                placeholder="Department name"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <button
                onClick={handleCreateDepartment}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Add Department
              </button>
            </div>
            {departments.length === 0 ? (
              <p className="text-sm text-gray-500">No departments yet.</p>
            ) : (
              <ul className="space-y-1 text-sm text-gray-700">
                {departments.map((d) => (
                  <li key={d.id}>
                    {d.dept_code} — {d.dept_name}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Cost Centers</h2>
            <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-4">
              <input
                type="text"
                value={centerForm.center_code}
                onChange={(e) => setCenterForm({ ...centerForm, center_code: e.target.value })}
                placeholder="Cost center code"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="text"
                value={centerForm.center_name}
                onChange={(e) => setCenterForm({ ...centerForm, center_name: e.target.value })}
                placeholder="Cost center name"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <select
                value={centerForm.department_id}
                onChange={(e) => setCenterForm({ ...centerForm, department_id: e.target.value })}
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              >
                <option value="">No department</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.dept_name}
                  </option>
                ))}
              </select>
              <button
                onClick={handleCreateCostCenter}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Add Cost Center
              </button>
            </div>
            {costCenters.length === 0 ? (
              <p className="text-sm text-gray-500">No cost centers yet.</p>
            ) : (
              <ul className="space-y-1 text-sm text-gray-700">
                {costCenters.map((c) => (
                  <li key={c.id}>
                    {c.center_code} — {c.center_name} ({departmentName(c.department_id)})
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Projects</h2>
            <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-5">
              <input
                type="text"
                value={projectForm.project_code}
                onChange={(e) => setProjectForm({ ...projectForm, project_code: e.target.value })}
                placeholder="Project code"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="text"
                value={projectForm.project_name}
                onChange={(e) => setProjectForm({ ...projectForm, project_name: e.target.value })}
                placeholder="Project name"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="date"
                value={projectForm.start_date}
                onChange={(e) => setProjectForm({ ...projectForm, start_date: e.target.value })}
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="number"
                value={projectForm.budget_amount}
                onChange={(e) =>
                  setProjectForm({ ...projectForm, budget_amount: e.target.value })
                }
                placeholder="Budget"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <button
                onClick={handleCreateProject}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Add Project
              </button>
            </div>
            {projects.length === 0 ? (
              <p className="text-sm text-gray-500">No projects yet.</p>
            ) : (
              <ul className="space-y-1 text-sm text-gray-700">
                {projects.map((p) => (
                  <li key={p.id}>
                    {p.project_code} — {p.project_name}
                    {p.budget_amount && ` (Budget: ${p.budget_amount})`}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
