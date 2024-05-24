package main

import (
	alerting "connaisseur/internal/alert"
	"connaisseur/internal/caching"
	"connaisseur/internal/config"
	"connaisseur/internal/constants"
	"connaisseur/internal/handler"
	"connaisseur/internal/utils"
	"context"
	"log"
	"net"
	"net/http"
	"os"
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/sirupsen/logrus"
	"k8s.io/client-go/dynamic"
	"k8s.io/client-go/rest"

	// Register the provider-specific plugins
	// if they are not imported here, their init() functions will not be called
	// and the provided kms functionality will not be available
	_ "github.com/sigstore/sigstore/pkg/signature/kms/aws"
	_ "github.com/sigstore/sigstore/pkg/signature/kms/azure"
	_ "github.com/sigstore/sigstore/pkg/signature/kms/gcp"
	_ "github.com/sigstore/sigstore/pkg/signature/kms/hashivault"
)

// Start a new HTTP server on port 5000 with /health, /ready,
// /metrics and /mutate routes. Takes a config and stores it inside
// its context.
func startServer(config *config.Config, alerting *alerting.Config) {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", handler.HandleHealth)
	mux.HandleFunc("/ready", handler.HandleHealth)
	mux.HandleFunc("/mutate", handler.HandleMutate)
	mux.HandleFunc("/metrics", promhttp.Handler().ServeHTTP)

	cache := caching.NewCacher()

	var apiClient dynamic.Interface
	if utils.FeatureFlagOn(constants.AutomaticChildApproval) {
		cfg, err := rest.InClusterConfig()
		if err != nil {
			logrus.Infof("error getting kubernetes api client config: %s", err)
		} else {
			apiClient, err = dynamic.NewForConfig(cfg)
			if err != nil {
				logrus.Infof("error creating kubernetes api client: %s", err)
			}
		}
	}

	ctx := context.Background()
	ctx = context.WithValue(ctx, constants.Logger, *logrus.StandardLogger())
	ctx = context.WithValue(ctx, constants.ConnaisseurConfig, config)
	ctx = context.WithValue(ctx, constants.AlertingConfig, alerting)
	ctx = context.WithValue(ctx, constants.Cache, cache)
	ctx = context.WithValue(ctx, constants.KubeAPI, apiClient)

	l := logrus.StandardLogger()
	errLog := log.New(l.WriterLevel(logrus.ErrorLevel), "", 0)

	server := &http.Server{
		Addr:         ":5000",
		Handler:      mux,
		ReadTimeout:  constants.HTTPTimeoutSeconds * time.Second,
		WriteTimeout: constants.HTTPTimeoutSeconds * time.Second,
		BaseContext: func(l net.Listener) context.Context {
			return ctx
		},
		ErrorLog: errLog,
	}

	// Set log outputs of relevant third party libraries
	utils.InitiateThirdPartyLibraryLogging()

	logrus.Info("Starting server at 127.0.0.1:5000...")
	if err := server.ListenAndServeTLS(constants.CertDir+"/tls.crt", constants.CertDir+"/tls.key"); err != nil {
		logrus.Fatal(err) // exits with code 1
	}
}

// Loads a Connaisseur config file from the filesystem
func loadConfigs() (*config.Config, *alerting.Config) {
	logrus.Debugf("Loading config from %s", constants.ConfigDir+"/config.yaml")
	config, err := config.Load(constants.ConfigDir, "/config.yaml")
	if err != nil {
		logrus.Fatalf("error loading config: %s", err) // exits with code 1
	}
	logrus.Debugf("Loading alerting config from %s", constants.AlertDir+"/config.yaml")
	alerting, err := alerting.LoadConfig(constants.AlertDir, "/config.yaml")
	if err != nil {
		logrus.Fatalf("error loading alerting config: %s", err) // exits with code 1
	}

	return config, alerting
}

// Main function
func main() {
	// set logging
	logrus.SetFormatter(&logrus.JSONFormatter{
		PrettyPrint: true,
	})
	logrus.SetOutput(os.Stdout)
	logrus.SetLevel(utils.ConnaisseurLogLevel())

	logrus.Debugf("Starting Connaisseur...")

	config, alerting := loadConfigs()
	startServer(config, alerting)
}
