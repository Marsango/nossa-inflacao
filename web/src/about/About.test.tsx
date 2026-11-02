import { render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from '../App';
import { Footer } from '../layout/Footer';

afterEach(() => { window.history.replaceState(null, '', '/'); vi.unstubAllGlobals(); });

it.each(['/sobre', '/sobre/'])('loads the about page directly at %s without fetching history', (path) => {
  window.history.replaceState(null, '', path);
  vi.stubGlobal('fetch', vi.fn());
  render(<App />);
  expect(screen.getByRole('heading', { level: 1, name: 'Sobre a Nossa inflação' })).toBeVisible();
  expect(screen.getByRole('region', { name: 'Sobre o projeto' })).toHaveAttribute('id', 'projeto');
  expect(screen.getByRole('region', { name: 'Sobre os dados e a metodologia' })).toHaveAttribute('id', 'metodologia');
  expect(screen.getByText(/O recorte monitorado não representa a inflação nacional/)).toBeVisible();
  expect(screen.getByRole('link', { name: '← Explorar preços' })).toHaveAttribute('href', '/');
  expect(fetch).not.toHaveBeenCalled();
});

it('replaces expanding footer sections with links and keeps the contribution link', () => {
  render(<Footer />);
  const footer = screen.getByRole('contentinfo');
  expect(within(footer).getByRole('link', { name: 'Sobre os dados e a metodologia' })).toHaveAttribute('href', '/sobre#metodologia');
  expect(within(footer).getByRole('link', { name: 'Sobre o projeto' })).toHaveAttribute('href', '/sobre#projeto');
  expect(within(footer).getByRole('link', { name: 'Contribua para o projeto' })).toHaveAttribute('href', 'https://github.com/Marsango/nossa-inflacao');
  expect(footer.querySelector('details')).toBeNull();
});

it('explains sparse observations, no future price backfill and the dates of retained comparisons', () => {
  window.history.replaceState(null, '', '/sobre#metodologia');
  render(<App />);
  expect(screen.getByRole('heading', { name: 'Como calculamos a visão geral' })).toBeVisible();
  expect(screen.getByText(/alta de 66,67% a partir do dia 30/)).toBeVisible();
  expect(screen.getByText(/Não exigimos um preço no começo do mês/)).toBeVisible();
  expect(screen.getByText(/a tabela mantém a data real da última observação usada/)).toBeVisible();
  expect(screen.getByText(/quantos produtos, lojas e contextos participaram/)).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Como calculamos o histórico de um produto' })).toBeVisible();
});
