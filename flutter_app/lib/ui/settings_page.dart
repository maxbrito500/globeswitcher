// Copyright 2026 Max Brito
// SPDX-License-Identifier: Apache-2.0

/// The settings panel the tray icon opens.
library;

import 'package:flutter/material.dart';

import '../model/settings.dart';

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key, required this.settings, required this.onClose});

  final SwitcherSettings settings;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('globeswitcher'),
          actions: [
            IconButton(
              tooltip: 'Close',
              onPressed: onClose,
              icon: const Icon(Icons.close),
            ),
          ],
          bottom: const TabBar(
            tabs: [
              Tab(text: 'Switcher'),
              Tab(text: 'About'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _SwitcherTab(settings: settings),
            const _AboutTab(),
          ],
        ),
      ),
    );
  }
}

class _SwitcherTab extends StatelessWidget {
  const _SwitcherTab({required this.settings});

  final SwitcherSettings settings;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: settings,
      builder: (context, _) => ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
        children: [
          Text('Changes take effect the next time you press Alt+Tab.',
              style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 12),
          for (final tunable in switcherTunables)
            _TunableSlider(settings: settings, tunable: tunable),
          const Divider(height: 32),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            value: settings.currentWorkspaceOnly,
            onChanged: settings.setCurrentWorkspaceOnly,
            title: const Text('Only this workspace'),
            subtitle: const Text(
                'Leave off to switch to windows on every workspace.'),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            value: settings.showTitles,
            onChanged: settings.setShowTitles,
            title: const Text('Show the window title'),
            subtitle: const Text(
                'The title of the window at the front, under the globe.'),
          ),
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerLeft,
            child: OutlinedButton.icon(
              onPressed: settings.restoreDefaults,
              icon: const Icon(Icons.restart_alt),
              label: const Text('Restore defaults'),
            ),
          ),
        ],
      ),
    );
  }
}

class _TunableSlider extends StatelessWidget {
  const _TunableSlider({required this.settings, required this.tunable});

  final SwitcherSettings settings;
  final Tunable tunable;

  @override
  Widget build(BuildContext context) {
    final value = settings.value(tunable.key);
    final theme = Theme.of(context);

    // Fractions read better as percentages; angles and times as themselves.
    final shown = tunable.unit.isEmpty
        ? '${(value * 100).round()}%'
        : '${value.toStringAsFixed(tunable.unit == 'ms' ? 0 : 2)}${tunable.unit}';

    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                  child: Text(tunable.label,
                      style: theme.textTheme.titleSmall)),
              Text(shown, style: theme.textTheme.bodyMedium),
            ],
          ),
          Slider(
            value: value,
            min: tunable.min,
            max: tunable.max,
            onChanged: (next) => settings.set(tunable.key, next),
          ),
          Text(tunable.help, style: theme.textTheme.bodySmall),
        ],
      ),
    );
  }
}

class _AboutTab extends StatelessWidget {
  const _AboutTab();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('globeswitcher', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 8),
        const Text(
            'Alt+Tab as a rotating Earth. Your open windows ride on a ring '
            'around the equator and turn with the globe, and the daylight on '
            'it is the daylight happening right now.'),
        const SizedBox(height: 20),
        Text('Keys', style: theme.textTheme.titleMedium),
        const SizedBox(height: 6),
        const Text('Alt+Tab — open, and roll the next window to the front\n'
            'Shift+Alt+Tab — roll the other way\n'
            'Arrow keys — keep rolling\n'
            'Release Alt — activate the window at the front\n'
            'Escape — close without switching\n'
            'w, q or F4 — close the window at the front'),
        const SizedBox(height: 20),
        Text('Imagery', style: theme.textTheme.titleMedium),
        const SizedBox(height: 6),
        const Text(
            'Blue Marble and Black Marble, courtesy of NASA Visible Earth. '
            'NASA imagery is in the public domain.'),
        const SizedBox(height: 20),
        Text('Licence', style: theme.textTheme.titleMedium),
        const SizedBox(height: 6),
        const Text('Apache License 2.0.'),
      ],
    );
  }
}
