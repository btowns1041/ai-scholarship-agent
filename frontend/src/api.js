import axios from "axios";

const client = axios.create({
  baseURL: "/api",
  timeout: 120000,
});

export async function fetchProfile() {
  const { data } = await client.get("/profile");
  return data;
}

export async function saveProfile(profile) {
  const { data } = await client.post("/profile", profile);
  return data;
}

export async function fetchScholarships(sortBy = "score", status) {
  const { data } = await client.get("/scholarships", {
    params: { sort_by: sortBy, status: status || undefined },
  });
  return data.scholarships || [];
}

export async function fetchMetrics() {
  const { data } = await client.get("/metrics");
  return data;
}

export async function updateStatus(id, status) {
  const { data } = await client.patch(`/scholarships/${id}/status`, { status });
  return data;
}

export async function scrapeAndEvaluate(payload) {
  const { data } = await client.post("/scrape-and-evaluate", payload);
  return data;
}

export async function rescore() {
  const { data } = await client.post("/rescore");
  return data;
}
