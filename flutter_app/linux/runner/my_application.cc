#include "my_application.h"

#include <flutter_linux/flutter_linux.h>
#ifdef GDK_WINDOWING_X11
#include <X11/Xlib.h>
#include <gdk/gdkx.h>
#endif

#include "flutter/generated_plugin_registrant.h"

struct _MyApplication {
  GtkApplication parent_instance;
  char** dart_entrypoint_arguments;
  GtkWindow* window;
};

// The switcher is an overlay, not an application window: it covers the screen,
// carries no decoration, stays above everything, and is only on screen while
// Alt is held. Dart drives that through this channel.
static const char* kWindowChannel = "globeswitcher/window";

G_DEFINE_TYPE(MyApplication, my_application, GTK_TYPE_APPLICATION)

// The window is deliberately not shown here: an Alt+Tab switcher that is on
// screen before Alt is pressed would be in the way of everything.
static void first_frame_cb(MyApplication* self, FlView* view) {}

#ifdef GDK_WINDOWING_X11
// Windows vanish while the switcher is asking about them, and GDK's handler
// treats any X error as fatal. The handler is process-wide and Xlib calls it
// from whatever thread the error arrives on, which is why it lives here in C
// rather than in Dart: a Dart callback reached with no Dart frame on the
// stack takes the whole process down.
static int swallow_x_error(Display* display, XErrorEvent* error) {
  return 0;
}
#endif

// The one window wears two hats. As the switcher it is an undecorated
// fullscreen overlay above everything; as the settings panel it is an ordinary
// window with a title bar. Flutter desktop gives an application a single
// window, so it is reconfigured rather than duplicated.
// The monitor the window is on, falling back to the first one.
static GdkMonitor* window_monitor(GtkWindow* window) {
  GdkDisplay* display = gtk_widget_get_display(GTK_WIDGET(window));
  GdkMonitor* monitor = gdk_display_get_primary_monitor(display);
  if (monitor == nullptr && gdk_display_get_n_monitors(display) > 0) {
    monitor = gdk_display_get_monitor(display, 0);
  }
  return monitor;
}

static void apply_overlay_mode(GtkWindow* window) {
  gtk_widget_hide(GTK_WIDGET(window));
  gtk_window_set_decorated(window, FALSE);

  // Resizable has to stay on. Marking the window fixed-size tells the window
  // manager it has a size of its own, and fullscreen is then only partly
  // honoured: coming back from the settings panel the overlay kept the
  // panel's width and covered half the screen.
  gtk_window_set_resizable(window, TRUE);
  gtk_window_set_skip_taskbar_hint(window, TRUE);
  gtk_window_set_skip_pager_hint(window, TRUE);
  gtk_window_set_keep_above(window, TRUE);
  gtk_window_set_type_hint(window, GDK_WINDOW_TYPE_HINT_SPLASHSCREEN);

  // Ask for fullscreen, but do not depend on it. A window manager is within
  // its rights to refuse fullscreen for a splash-hinted window, and when it
  // does the overlay keeps whatever size it had -- which showed up as the
  // switcher covering only part of the screen. Setting the monitor's own
  // geometry makes the coverage true either way.
  GdkMonitor* monitor = window_monitor(window);
  if (monitor != nullptr) {
    GdkRectangle area;
    gdk_monitor_get_geometry(monitor, &area);
    gtk_window_move(window, area.x, area.y);
    gtk_window_resize(window, area.width, area.height);
  }
  gtk_window_fullscreen(window);
  gtk_widget_show(GTK_WIDGET(window));
  gtk_window_present(window);
}


// Sized from the screen rather than fixed: a panel of sliders wants room, and
// a size that suits a laptop leaves a desktop monitor looking half empty.
static void settings_size(GtkWindow* window, int* width, int* height) {
  GdkRectangle area = {0, 0, 1280, 800};
  GdkMonitor* monitor = window_monitor(window);
  if (monitor != nullptr) {
    gdk_monitor_get_workarea(monitor, &area);
  }

  *width = CLAMP((int)(area.width * 0.66), 900, 1500);
  *height = CLAMP((int)(area.height * 0.86), 700, 1150);
}

// Leaving fullscreen is asynchronous, so a resize issued in the same breath is
// applied and then undone by the window manager finishing the unfullscreen --
// which left the settings panel filling the screen. Doing it once more after
// the window is up settles it at the size actually asked for.
static gboolean settle_settings_size(gpointer data) {
  GtkWindow* window = GTK_WINDOW(data);
  int width = 0;
  int height = 0;
  settings_size(window, &width, &height);
  gtk_window_resize(window, width, height);
  return G_SOURCE_REMOVE;
}

static void apply_settings_mode(GtkWindow* window) {
  int width = 0;
  int height = 0;
  settings_size(window, &width, &height);

  gtk_widget_hide(GTK_WIDGET(window));
  gtk_window_unfullscreen(window);
  gtk_window_set_keep_above(window, FALSE);
  gtk_window_set_type_hint(window, GDK_WINDOW_TYPE_HINT_NORMAL);
  gtk_window_set_skip_taskbar_hint(window, FALSE);
  gtk_window_set_skip_pager_hint(window, FALSE);
  gtk_window_set_decorated(window, TRUE);
  gtk_window_set_resizable(window, TRUE);
  gtk_window_set_default_size(window, width, height);
  gtk_window_resize(window, width, height);
  gtk_window_set_position(window, GTK_WIN_POS_CENTER);
  gtk_widget_show(GTK_WIDGET(window));
  gtk_window_present(window);
  g_timeout_add(80, settle_settings_size, window);
}

static void window_method_call_cb(FlMethodChannel* channel,
                                  FlMethodCall* method_call,
                                  gpointer user_data) {
  MyApplication* self = MY_APPLICATION(user_data);
  const gchar* method = fl_method_call_get_name(method_call);
  g_autoptr(FlMethodResponse) response = nullptr;

  if (g_strcmp0(method, "setMode") == 0 && self->window != nullptr) {
    FlValue* args = fl_method_call_get_args(method_call);
    const gchar* mode = fl_value_get_type(args) == FL_VALUE_TYPE_STRING
                            ? fl_value_get_string(args)
                            : "hidden";

    if (g_strcmp0(mode, "overlay") == 0) {
      apply_overlay_mode(self->window);
    } else if (g_strcmp0(mode, "settings") == 0) {
      apply_settings_mode(self->window);
    } else {
      gtk_widget_hide(GTK_WIDGET(self->window));
    }
    response = FL_METHOD_RESPONSE(fl_method_success_response_new(nullptr));
  } else {
    response = FL_METHOD_RESPONSE(fl_method_not_implemented_response_new());
  }

  g_autoptr(GError) error = nullptr;
  if (!fl_method_call_respond(method_call, response, &error)) {
    g_warning("globeswitcher: failed to respond: %s", error->message);
  }
}

// Implements GApplication::activate.
static void my_application_activate(GApplication* application) {
  MyApplication* self = MY_APPLICATION(application);
  GtkWindow* window =
      GTK_WINDOW(gtk_application_window_new(GTK_APPLICATION(application)));

  // Use a header bar when running in GNOME as this is the common style used
  // by applications and is the setup most users will be using (e.g. Ubuntu
  // desktop).
  // If running on X and not using GNOME then just use a traditional title bar
  // in case the window manager does more exotic layout, e.g. tiling.
  // If running on Wayland assume the header bar will work (may need changing
  // if future cases occur).
  self->window = window;

#ifdef GDK_WINDOWING_X11
  if (GDK_IS_X11_DISPLAY(gtk_widget_get_display(GTK_WIDGET(window)))) {
    XSetErrorHandler(swallow_x_error);
  }
#endif

  // No decoration, no taskbar entry, no pager entry, always on top, and the
  // size of the screen: an overlay rather than a window.
  gtk_window_set_title(window, "globeswitcher");
  gtk_window_set_decorated(window, FALSE);
  gtk_window_set_skip_taskbar_hint(window, TRUE);
  gtk_window_set_skip_pager_hint(window, TRUE);
  gtk_window_set_keep_above(window, TRUE);
  gtk_window_set_type_hint(window, GDK_WINDOW_TYPE_HINT_SPLASHSCREEN);
  gtk_window_fullscreen(window);

  g_autoptr(FlDartProject) project = fl_dart_project_new();
  fl_dart_project_set_dart_entrypoint_arguments(
      project, self->dart_entrypoint_arguments);

  FlView* view = fl_view_new(project);
  GdkRGBA background_color;
  // Background defaults to black, override it here if necessary, e.g. #00000000
  // for transparent.
  gdk_rgba_parse(&background_color, "#000000");
  fl_view_set_background_color(view, &background_color);
  gtk_widget_show(GTK_WIDGET(view));
  gtk_container_add(GTK_CONTAINER(window), GTK_WIDGET(view));

  // Show the window when Flutter renders.
  // Requires the view to be realized so we can start rendering.
  g_signal_connect_swapped(view, "first-frame", G_CALLBACK(first_frame_cb),
                           self);
  gtk_widget_realize(GTK_WIDGET(view));

  fl_register_plugins(FL_PLUGIN_REGISTRY(view));

  g_autoptr(FlStandardMethodCodec) codec = fl_standard_method_codec_new();
  FlMethodChannel* channel = fl_method_channel_new(
      fl_engine_get_binary_messenger(fl_view_get_engine(view)), kWindowChannel,
      FL_METHOD_CODEC(codec));
  fl_method_channel_set_method_call_handler(channel, window_method_call_cb,
                                            g_object_ref(self),
                                            g_object_unref);

  gtk_widget_grab_focus(GTK_WIDGET(view));
}

// Implements GApplication::local_command_line.
static gboolean my_application_local_command_line(GApplication* application,
                                                  gchar*** arguments,
                                                  int* exit_status) {
  MyApplication* self = MY_APPLICATION(application);
  // Strip out the first argument as it is the binary name.
  self->dart_entrypoint_arguments = g_strdupv(*arguments + 1);

  g_autoptr(GError) error = nullptr;
  if (!g_application_register(application, nullptr, &error)) {
    g_warning("Failed to register: %s", error->message);
    *exit_status = 1;
    return TRUE;
  }

  g_application_activate(application);
  *exit_status = 0;

  return TRUE;
}

// Implements GApplication::startup.
static void my_application_startup(GApplication* application) {
  // MyApplication* self = MY_APPLICATION(object);

  // Perform any actions required at application startup.

  G_APPLICATION_CLASS(my_application_parent_class)->startup(application);
}

// Implements GApplication::shutdown.
static void my_application_shutdown(GApplication* application) {
  // MyApplication* self = MY_APPLICATION(object);

  // Perform any actions required at application shutdown.

  G_APPLICATION_CLASS(my_application_parent_class)->shutdown(application);
}

// Implements GObject::dispose.
static void my_application_dispose(GObject* object) {
  MyApplication* self = MY_APPLICATION(object);
  g_clear_pointer(&self->dart_entrypoint_arguments, g_strfreev);
  G_OBJECT_CLASS(my_application_parent_class)->dispose(object);
}

static void my_application_class_init(MyApplicationClass* klass) {
  G_APPLICATION_CLASS(klass)->activate = my_application_activate;
  G_APPLICATION_CLASS(klass)->local_command_line =
      my_application_local_command_line;
  G_APPLICATION_CLASS(klass)->startup = my_application_startup;
  G_APPLICATION_CLASS(klass)->shutdown = my_application_shutdown;
  G_OBJECT_CLASS(klass)->dispose = my_application_dispose;
}

static void my_application_init(MyApplication* self) {}

MyApplication* my_application_new() {
  // Set the program name to the application ID, which helps various systems
  // like GTK and desktop environments map this running application to its
  // corresponding .desktop file. This ensures better integration by allowing
  // the application to be recognized beyond its binary name.
  g_set_prgname(APPLICATION_ID);

  return MY_APPLICATION(g_object_new(my_application_get_type(),
                                     "application-id", APPLICATION_ID, "flags",
                                     G_APPLICATION_NON_UNIQUE, nullptr));
}
